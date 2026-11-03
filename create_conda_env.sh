#!/usr/bin/env bash
# Install conda if needed, then create (or update) a project-local environment,
# register a Jupyter kernel, and apply patches to pymc3-quap and causalgraphicalmodels.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_PREFIX="$PROJECT_ROOT/.conda"
ENV_FILE="$PROJECT_ROOT/environment.yml"
KERNEL_NAME="fnds"
MINIFORGE_DIR="${MINIFORGE_DIR:-$HOME/miniforge3}"

install_miniforge() {
    local os arch installer url
    os="$(uname -s)"
    arch="$(uname -m)"

    case "$os" in
        Linux)
            url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-${arch}.sh"
            ;;
        Darwin)
            url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-${arch}.sh"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            echo "Windows detected. Installing Miniforge with winget..."
            winget install -e --id CondaForge.Miniforge3 --accept-package-agreements --accept-source-agreements
            echo "Miniforge installed. Open a new terminal and rerun this script."
            exit 0
            ;;
        *)
            echo "Unsupported OS: $os" >&2
            exit 1
            ;;
    esac

    echo "Downloading Miniforge for ${os} (${arch})..."
    installer="$(mktemp "${TMPDIR:-/tmp}/miniforge.XXXXXX.sh")"
    curl -fsSL "$url" -o "$installer"
    bash "$installer" -b -p "$MINIFORGE_DIR"
    rm -f "$installer"
    echo "Miniforge installed to $MINIFORGE_DIR"
}

CONDA="$(command -v conda || true)"
if [[ -z "$CONDA" ]]; then
    if [[ ! -x "$MINIFORGE_DIR/bin/conda" ]]; then
        install_miniforge
    fi
    CONDA="$MINIFORGE_DIR/bin/conda"
fi

if [[ -d "$ENV_PREFIX" ]]; then
    echo "Updating environment at $ENV_PREFIX..."
    "$CONDA" env update --prefix "$ENV_PREFIX" --file "$ENV_FILE" --prune
else
    echo "Creating environment at $ENV_PREFIX..."
    "$CONDA" env create --prefix "$ENV_PREFIX" --file "$ENV_FILE"
fi

echo "Registering Jupyter kernel..."
"$CONDA" run --prefix "$ENV_PREFIX" python -m ipykernel install --user \
    --name="$KERNEL_NAME" --display-name="Python ($KERNEL_NAME)"

echo "Patching pymc3-quap..."
QUAP_LOCATION="$("$CONDA" run --prefix "$ENV_PREFIX" python -m pip show pymc3-quap \
    | awk '/^Location:/{print $2}')"
sed -i.bak 's/pymc3/pymc/g' "$QUAP_LOCATION/quap/quap.py"

echo "Patching causalgraphicalmodels..."
CGM_LOCATION="$("$CONDA" run --prefix "$ENV_PREFIX" python -m pip show causalgraphicalmodels \
    | awk '/^Location:/{print $2}')"
sed -i.bak 's/from collections import Iterable/from collections.abc import Iterable/' \
    "$CGM_LOCATION/causalgraphicalmodels/cgm.py"

echo "Done. In Jupyter, select: Python ($KERNEL_NAME)"