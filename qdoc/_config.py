import hashlib
import re
import shutil
from importlib.metadata import version as get_version
from importlib.resources import files as _files
from pathlib import Path

DOC_DIR = Path(__file__).parent

# The environment file holds the version
ENV_TPL = """\
VERSION={version}
"""


def generate_environment_file():
    """
    Generate _enviroment file in the quartodoc project directory
    """
    version = get_version("plotnine")
    filepath = DOC_DIR / "_environment"

    # The scm-version scheme adds .date suffix to the version
    # if the repo is dirty. For better look while developing,
    # we remove it.
    dirty_pattern = re.compile(r"\.d\d{8}$")
    if dirty_pattern.search(version):
        version = dirty_pattern.sub("", version)

    # FIXME: We return because modifying the _environment file
    # breaks "quarto render"
    if filepath.exists():
        return

    contents = ENV_TPL.format(version=version)
    filepath.write_text(contents)


def copy_tutorials():
    """
    Copy the tutorials in plotnine_examples
    """

    # NOTE: To avoid confusing the watcher used by "quarto preview",
    # we copy only if the original files are different.
    def same_contents(f1, f2):
        h1 = hashlib.md5(f1.read_bytes()).hexdigest()
        h2 = hashlib.md5(f2.read_bytes()).hexdigest()
        return h1 == h2

    src_dir = _files("plotnine_examples.tutorials")
    dest_dir = DOC_DIR / "tutorials"

    src_files = src_dir.glob("*.ipynb")  # type: ignore
    cur_dest_files = dest_dir.glob("*.ipynb")
    new_dest_files = []

    for src in src_files:
        dest = dest_dir / src.name
        new_dest_files.append(dest)
        if dest.exists() and same_contents(src, dest):
            continue
        shutil.copyfile(src, dest)

    # Remove any deleted files
    for dest in set(cur_dest_files).difference(new_dest_files):
        dest.unlink()


if __name__ == "__main__":
    generate_environment_file()
    copy_tutorials()