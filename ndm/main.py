import os
import venv
from pathlib import Path

import sh
import tomli
import tomli_w
import typer
from jinja2 import Environment, PackageLoader, select_autoescape
from rich import print
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer()

ROOT_PROJECT = Path().absolute()
PYPROJECT_FILENAME = "pyproject.toml"
REQUIREMENTS_FILENAME = "requirements.txt"
VENV_FOLDER_NAME = "venv"

VENV_BIN_PATH = Path(VENV_FOLDER_NAME).joinpath("bin")
VENV_PIP_PATH = VENV_BIN_PATH.joinpath("pip")
VENV_PYTHON_EXEC_PATH = VENV_BIN_PATH.joinpath("python")

env_builder = venv.EnvBuilder(with_pip=True, prompt=VENV_FOLDER_NAME)
jinja_env = Environment(loader=PackageLoader("ndm"), autoescape=select_autoescape())

pip = sh.Command("pip")
pip_compile = sh.Command("pip-compile")
pip_sync = sh.Command("pip-sync")


TomlDoc = dict


def create_pyproject_file(pyproject_content: str):
    toml_dict: TomlDoc = tomli.loads(pyproject_content)
    create_or_update(toml_dict)


def render_pyproject(name: str, requires_python: str) -> str:
    template = jinja_env.get_template(f"{PYPROJECT_FILENAME}.template")
    return template.render(name=name, requires_python=requires_python)


def get(project_file_name: str) -> TomlDoc:
    "Get a toml file data"

    with open(project_file_name, "rb") as f:
        toml_dict = tomli.load(f)
        return toml_dict


def create_or_update(doc: TomlDoc):
    """Update the pyproject.toml"""

    with open("pyproject.toml", "w") as f:
        f.write(tomli_w.dumps(doc))


def create_venv():
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Creating virtual environment...")
        env_builder.create(VENV_FOLDER_NAME)


@app.command()
def init():
    """Create a initial pyproject.toml in project root"""

    if os.path.exists(PYPROJECT_FILENAME):
        print("[bold red]Error[/bold red]: pyproject already exists")
        return

    name: str = typer.prompt("Project name")
    requires_python: str = typer.prompt("Python version requirement")
    pyproject_content: str = render_pyproject(name, requires_python)
    create_pyproject_file(pyproject_content)


@app.command()
def add(package_names: list[str], dev: bool = False):
    """Add a package in pyproject.toml"""

    toml_doc = get(PYPROJECT_FILENAME)
    if dev:
        toml_doc["project"]["optional-dependencies"]["dev"].extend(package_names)
    else:
        toml_doc["project"]["dependencies"].extend(package_names)
    create_or_update(toml_doc)


@app.command()
def remove(package_name: str, dev: bool = False):
    """Remove a package in pyproject.toml"""

    toml_doc: TomlDoc = get(PYPROJECT_FILENAME)

    if dev:
        package_list = toml_doc["project"]["optional-dependencies"]["dev"]
    else:
        package_list = toml_doc["project"]["dependencies"]

    one_or_empty = [pkg for pkg in package_list if package_name in pkg]
    if one_or_empty:
        package_list.remove(one_or_empty[0])
        create_or_update(toml_doc)
        return
    print("[bold red]Error[/bold red]: package not found")


@app.command()
def compile(dev: bool = False):
    """Compiles requirements.txt from pyproject dependencies"""

    options: list = [
        "--generate-hashes",
        "-o",
        REQUIREMENTS_FILENAME,
        PYPROJECT_FILENAME,
    ]
    if dev:
        options = ["--extra", "dev"] + options
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Compiling requirements.txt...")
        pip_compile(*options)


@app.command()
def sync(dev: bool = False, comp: bool = True, venv: bool = True):
    """Synchronize environment with requirements.txt."""

    if comp:
        compile(dev)

    python_exec_opt = ''
    if venv:
        if not os.path.exists(VENV_FOLDER_NAME):
            create_venv()
        python_exec_opt = f'--python-executable {VENV_PYTHON_EXEC_PATH}'

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Synchronizing...")
        pip_sync(python_exec_opt)


@app.command()
def install(dev: bool = False, syn: bool = False, venv: bool = True):
    """
    Create isolated environment (or not) and install packages from requirements.txt
    """

    pip_cmd = pip
    compile(dev)

    if venv:
        if not os.path.exists(VENV_FOLDER_NAME):
            create_venv()
        pip_cmd = sh.Command(VENV_PIP_PATH)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Installing packages...")
        pip_cmd("install", "-r", REQUIREMENTS_FILENAME)
        if syn:
            sync(dev, False, venv)


@app.command()
def test():
    print(Path().absolute().joinpath(VENV_FOLDER_NAME))
