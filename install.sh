#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# zotero-paper-report-skill — One-Click Installer
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

SKILL_NAME="zotero-paper-report"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

# Defaults
ENV_TYPE="uv"
ENV_NAME=".venv-zpr"
PYTHON_VERSION="3.10"
ZOTERO_PORT=""
AGENT="claude"
SKILL_ONLY=false

# --- Helper functions ---

print_ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
print_err()  { echo -e "  ${RED}✗${NC} $1"; }
print_info() { echo -e "  ${CYAN}→${NC} $1"; }
banner()     { echo -e "\n${CYAN}===${NC} $1 ${CYAN}===${NC}"; }

usage() {
    cat <<EOF
Usage: install.sh [options]

One-click installer for zotero-paper-report skill, dependencies, and Python CLI.

Options:
  --env <type>        Virtual environment type (default: uv)
                      uv    - Use uv venv (recommended)
                      conda - Use conda/miniconda
                      venv  - Use python3 -m venv
  --skill-only        Install only skill files (skip venv, Python deps, MCP config)
  --env-name <name>   Virtual environment name (default: .venv-zpr)
  --python <ver>      Python version for venv (default: 3.10)
  --zotero-port <p>   Zotero local API port (auto-detected if not specified)
  --agent <name>      Target coding agent (default: claude)
                      Reserved for future: opencode
  --help              Show this help message

Examples:
  ./install.sh                                  # Full install with uv venv
  ./install.sh --env conda                      # Full install with conda
  ./install.sh --skill-only                     # Skills only, no Python env
  ./install.sh --env-name "zpr-prod"            # Custom env name
  ./install.sh --zotero-port 23120              # Specify Zotero port
EOF
    exit 0
}

# --- Argument parsing ---

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)
            ENV_TYPE="$2"
            if [[ "$ENV_TYPE" != "uv" && "$ENV_TYPE" != "conda" && "$ENV_TYPE" != "venv" ]]; then
                echo -e "${RED}Error: --env must be uv, conda, or venv${NC}"
                exit 1
            fi
            shift 2
            ;;
        --skill-only)
            SKILL_ONLY=true
            shift
            ;;
        --env-name)
            ENV_NAME="$2"
            shift 2
            ;;
        --python)
            PYTHON_VERSION="$2"
            shift 2
            ;;
        --zotero-port)
            ZOTERO_PORT="$2"
            shift 2
            ;;
        --agent)
            AGENT="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# --- Agent dispatch ---

if [[ "$AGENT" != "claude" ]]; then
    echo -e "${YELLOW}Agent '$AGENT' is not yet supported.${NC}"
    echo "Currently only 'claude' is available. opencode support is planned for a future release."
    exit 0
fi

MCP_FILE="$HOME/.claude/.mcp.json"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
PYTHON_DIR="$SCRIPT_DIR/python"
PDF_SKILL_SRC="$SCRIPT_DIR/3rdparty/anthropics-skills/skills/pdf"

# ============================================================
# Step 1/6: Check prerequisites
# ============================================================
banner "Step 1/6: Checking prerequisites"

MISSING=0
BLOCKING=0

# Claude CLI (user-managed)
if command -v "$CLAUDE_BIN" &>/dev/null; then
    print_ok "claude CLI found"
else
    print_err "claude CLI not found"
    print_info "Install Claude Code: https://docs.anthropic.com/en/docs/claude-code"
    MISSING=$((MISSING + 1))
fi

# npm (user-managed, needed for zotero-mcp)
if command -v npm &>/dev/null; then
    print_ok "npm found"
else
    print_err "npm not found (required for zotero-mcp)"
    print_info "Install Node.js: https://nodejs.org/"
    MISSING=$((MISSING + 1))
fi

# Env tool check
if ! $SKILL_ONLY; then
    case "$ENV_TYPE" in
        uv)
            if command -v uv &>/dev/null; then
                print_ok "uv found"
            else
                print_err "uv not found"
                print_info "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
                print_info "Or use --env conda / --env venv"
                BLOCKING=$((BLOCKING + 1))
            fi
            ;;
        conda)
            if command -v conda &>/dev/null; then
                print_ok "conda found"
            else
                print_err "conda not found"
                print_info "Install miniconda: https://docs.conda.io/en/latest/miniconda.html"
                print_info "Or use --env uv / --env venv"
                BLOCKING=$((BLOCKING + 1))
            fi
            ;;
        venv)
            if command -v python3 &>/dev/null; then
                print_ok "python3 found"
            else
                print_err "python3 not found"
                print_info "Install Python 3.10+: https://www.python.org/"
                BLOCKING=$((BLOCKING + 1))
            fi
            ;;
    esac
fi

echo ""
if [ $BLOCKING -gt 0 ]; then
    echo -e "${RED}Error: $BLOCKING required tool(s) missing. Install them or use a different --env option.${NC}"
    exit 1
fi
if [ $MISSING -gt 0 ]; then
    echo -e "${YELLOW}Warning: $MISSING tool(s) missing. Please install them before using the skill.${NC}"
    echo ""
fi

# ============================================================
# Step 2/6: Check submodule
# ============================================================
banner "Step 2/6: Checking vendored dependencies"

if [ -f "$PDF_SKILL_SRC/SKILL.md" ]; then
    print_ok "pdf skill (vendored)"
else
    print_err "pdf skill submodule not found"
    print_info "Run: git submodule update --init --recursive"
    exit 1
fi

# ============================================================
# Step 3/6: Create virtual environment + install Python deps
# ============================================================
if $SKILL_ONLY; then
    banner "Step 3/6: Python environment (SKIPPED — --skill-only)"
else
    banner "Step 3/6: Setting up Python environment ($ENV_TYPE)"

    ENV_PATH="$SCRIPT_DIR/$ENV_NAME"

    # Check name conflict
    if [ -d "$ENV_PATH" ]; then
        print_warn "'$ENV_NAME' already exists at $ENV_PATH"
        echo ""
        read -r -p "  Continue using existing environment? [y/N] " yn
        case "$yn" in
            [Yy]* )
                print_info "Using existing environment"
                ;;
            * )
                print_info "Use --env-name <name> to specify a different name,"
                print_info "or delete '$ENV_PATH' and re-run."
                exit 0
                ;;
        esac
    fi

    # Also check conda env list
    if [[ "$ENV_TYPE" == "conda" ]] && command -v conda &>/dev/null; then
        if conda env list 2>/dev/null | grep -q "^${ENV_NAME} "; then
            print_warn "Conda environment '$ENV_NAME' already exists"
            echo ""
            read -r -p "  Continue using existing environment? [y/N] " yn
            case "$yn" in
                [Yy]* )
                    print_info "Using existing conda environment"
                    ;;
                * )
                    print_info "Use --env-name <name> to specify a different name."
                    exit 0
                    ;;
            esac
        fi
    fi

    # Create environment
    if [[ "$ENV_TYPE" == "uv" ]]; then
        if [ ! -d "$ENV_PATH" ]; then
            print_info "Creating uv virtual environment: $ENV_NAME"
            uv venv --python "$PYTHON_VERSION" "$ENV_NAME" 2>&1 | while IFS= read -r line; do
                [ -n "$line" ] && echo "    $line"
            done
            print_ok "Virtual environment created"
        fi

        source "$ENV_PATH/bin/activate"
        print_info "Installing Python dependencies..."
        uv pip install -r "$REQUIREMENTS_FILE" 2>&1 | while IFS= read -r line; do
            [ -n "$line" ] && echo "    $line"
        done
        print_ok "Dependencies installed"

        print_info "Installing zotero-paper-report CLI..."
        uv pip install -e "$PYTHON_DIR" 2>&1 | while IFS= read -r line; do
            [ -n "$line" ] && echo "    $line"
        done
        print_ok "zotero-paper-report CLI installed"

    elif [[ "$ENV_TYPE" == "conda" ]]; then
        if ! conda env list 2>/dev/null | grep -q "^${ENV_NAME} "; then
            print_info "Creating conda environment: $ENV_NAME"
            conda create -n "$ENV_NAME" python="$PYTHON_VERSION" -y 2>&1 | while IFS= read -r line; do
                [ -n "$line" ] && echo "    $line"
            done
            print_ok "Conda environment created"
        fi

        eval "$(conda shell.bash hook)"
        conda activate "$ENV_NAME"
        print_info "Installing Python dependencies..."
        pip install -r "$REQUIREMENTS_FILE" 2>&1 | while IFS= read -r line; do
            [ -n "$line" ] && echo "    $line"
        done
        print_ok "Dependencies installed"

        print_info "Installing zotero-paper-report CLI..."
        pip install -e "$PYTHON_DIR" 2>&1 | while IFS= read -r line; do
            [ -n "$line" ] && echo "    $line"
        done
        print_ok "zotero-paper-report CLI installed"

    elif [[ "$ENV_TYPE" == "venv" ]]; then
        if [ ! -d "$ENV_PATH" ]; then
            print_info "Creating venv: $ENV_NAME"
            python3 -m venv "$ENV_PATH"
            print_ok "venv created"
        fi

        source "$ENV_PATH/bin/activate"
        print_info "Installing Python dependencies..."
        pip install -r "$REQUIREMENTS_FILE" 2>&1 | while IFS= read -r line; do
            [ -n "$line" ] && echo "    $line"
        done
        print_ok "Dependencies installed"

        print_info "Installing zotero-paper-report CLI..."
        pip install -e "$PYTHON_DIR" 2>&1 | while IFS= read -r line; do
            [ -n "$line" ] && echo "    $line"
        done
        print_ok "zotero-paper-report CLI installed"
    fi
fi

# ============================================================
# Step 4/6: Configure zotero-mcp
# ============================================================
banner "Step 4/6: Configuring zotero-mcp"

_resolve_port() {
    # Priority: --zotero-port flag > auto-detect > interactive prompt
    # Diagnostics go to stderr so only the port number is captured on stdout.
    local detected=""

    if [ -n "$ZOTERO_PORT" ]; then
        detected="$ZOTERO_PORT"
        echo -e "  ${GREEN}✓${NC} Using specified port: $detected" >&2
        echo "$detected"
        return
    fi

    # Step A: curl default port
    echo -e "  ${CYAN}→${NC} Probing default Zotero port (23119)..." >&2
    if curl -s --connect-timeout 2 "http://localhost:23119" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Zotero detected on port 23119" >&2
        echo "23119"
        return
    fi

    # Step B: lsof
    echo -e "  ${CYAN}→${NC} Searching for Zotero process..." >&2
    detected=$(lsof -i -P -n 2>/dev/null | grep -i zotero | grep LISTEN | \
               awk '{print $9}' | sed 's/.*://' | head -1)
    if [ -n "$detected" ]; then
        echo -e "  ${GREEN}✓${NC} Zotero detected on port $detected (via lsof)" >&2
        echo "$detected"
        return
    fi

    # Step C: interactive prompt (to stderr since we're capturing stdout)
    echo "" >&2
    echo -e "  ${YELLOW}⚠${NC} Could not auto-detect Zotero port." >&2
    echo "" >&2
    echo "  Please check your Zotero port:" >&2
    echo "    Zotero → Preferences → Advanced → Config Editor" >&2
    echo "    Search for: extensions.zotero.debug.store" >&2
    echo "    More info: https://github.com/cookjohn/zotero-mcp/blob/main/README-zh.md" >&2
    echo "" >&2
    read -r -p "  Enter Zotero port number (default: 23119): " detected
    [ -z "$detected" ] && detected="23119"
    echo "$detected"
}

ZOTERO_PORT=$(_resolve_port)

# Write MCP config
mkdir -p "$(dirname "$MCP_FILE")"

if [ -f "$MCP_FILE" ]; then
    if grep -q '"zotero"' "$MCP_FILE" 2>/dev/null; then
        print_ok "zotero already configured in .mcp.json, skipping"
    elif command -v jq &>/dev/null; then
        # Use jq for safe merge
        jq --arg port "$ZOTERO_PORT" \
           '.mcpServers.zotero = {
                "command": "npx",
                "args": ["-y", "zotero-mcp"],
                "env": {"ZOTERO_BASE_URL": ("http://localhost:" + $port)}
            }' "$MCP_FILE" > "${MCP_FILE}.tmp" && mv "${MCP_FILE}.tmp" "$MCP_FILE"
        print_ok "Added zotero to .mcp.json (port: $ZOTERO_PORT)"
    else
        print_warn "jq not available — cannot safely merge MCP config"
        print_info "Please add the following to $MCP_FILE:"
        cat <<MCFG
{
  "mcpServers": {
    "zotero": {
      "command": "npx",
      "args": ["-y", "zotero-mcp"],
      "env": {
        "ZOTERO_BASE_URL": "http://localhost:${ZOTERO_PORT}"
      }
    }
  }
}
MCFG
    fi
else
    # Create new config
    cat > "$MCP_FILE" <<MCFG
{
  "mcpServers": {
    "zotero": {
      "command": "npx",
      "args": ["-y", "zotero-mcp"],
      "env": {
        "ZOTERO_BASE_URL": "http://localhost:${ZOTERO_PORT}"
      }
    }
  }
}
MCFG
    print_ok "Created .mcp.json with zotero config (port: $ZOTERO_PORT)"
fi

# ============================================================
# Step 5/6: Install skills
# ============================================================
banner "Step 5/6: Installing skills"

mkdir -p "$SKILLS_DIR"

# zotero-paper-report
ZPR_SRC="$SCRIPT_DIR/zotero-paper-report"
ZPR_DST="$SKILLS_DIR/zotero-paper-report"
rm -rf "$ZPR_DST"
cp -r "$ZPR_SRC" "$ZPR_DST"
print_ok "Installed zotero-paper-report -> $ZPR_DST"

# pdf skill from 3rdparty
PDF_DST="$SKILLS_DIR/pdf"
rm -rf "$PDF_DST"
cp -r "$PDF_SKILL_SRC" "$PDF_DST"
print_ok "Installed pdf skill            -> $PDF_DST"

# scientific-writer from GitHub
SW_DST="$SKILLS_DIR/scientific-writing"
if [ -f "$SW_DST/SKILL.md" ]; then
    print_ok "scientific-writing already exists, skipping"
else
    print_info "Cloning claude-scientific-writer..."
    if git clone --depth 1 \
        https://github.com/K-Dense-AI/claude-scientific-writer.git \
        "$SW_DST" 2>&1 | while IFS= read -r line; do
        [ -n "$line" ] && echo "    $line"
    done; then
        # The repo has nested skill dirs; SKILL.md may be in a subdirectory
        if [ -f "$SW_DST/SKILL.md" ]; then
            print_ok "Installed scientific-writing   -> $SW_DST"
        elif [ -f "$SW_DST/.claude/skills/scientific-writing/SKILL.md" ]; then
            # Move the actual skill dir up
            mv "$SW_DST/.claude/skills/scientific-writing" "$SKILLS_DIR/scientific-writing-tmp"
            rm -rf "$SW_DST"
            mv "$SKILLS_DIR/scientific-writing-tmp" "$SW_DST"
            print_ok "Installed scientific-writing   -> $SW_DST"
        else
            print_ok "cloned (SKILL.md in subdirectory)"
        fi
    else
        print_warn "Failed to clone scientific-writer"
        print_info "Install manually: https://github.com/K-Dense-AI/claude-scientific-writer"
    fi
fi

# ============================================================
# Step 6/6: Verify
# ============================================================
banner "Step 6/6: Verifying installation"

FAIL=0

# Skill files
for skill in "$ZPR_DST" "$PDF_DST" "$SW_DST"; do
    skill_name=$(basename "$skill")
    if [ -f "$skill/SKILL.md" ]; then
        print_ok "$skill_name/SKILL.md"
    else
        print_warn "$skill_name/SKILL.md — MISSING (may need manual install)"
        FAIL=$((FAIL + 1))
    fi
done

# MCP config
if [ -f "$MCP_FILE" ] && grep -q '"zotero"' "$MCP_FILE" 2>/dev/null; then
    print_ok "zotero-mcp in .mcp.json"
else
    print_warn "zotero-mcp NOT in .mcp.json"
    FAIL=$((FAIL + 1))
fi

# CLI
if ! $SKILL_ONLY; then
    if command -v zotero-paper-report &>/dev/null; then
        print_ok "zotero-paper-report CLI"
    else
        print_warn "zotero-paper-report CLI not on PATH"
        print_info "Activate your environment first, then retry."
    fi
fi

# ============================================================
# Summary
# ============================================================
echo ""
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ Installation complete!${NC}"
    echo ""
    echo -e "  ${BOLD}Skills:${NC}      zotero-paper-report, pdf, scientific-writing"
    echo -e "  ${BOLD}MCP server:${NC}  zotero (port: $ZOTERO_PORT)"
    if ! $SKILL_ONLY; then
        echo -e "  ${BOLD}CLI:${NC}         zotero-paper-report"
        echo -e "  ${BOLD}Env:${NC}         $ENV_NAME ($ENV_TYPE)"
        echo ""
        echo -e "  ${BOLD}To use CLI:${NC}"
        if [[ "$ENV_TYPE" == "conda" ]]; then
            echo -e "    ${CYAN}conda activate $ENV_NAME${NC}"
        else
            echo -e "    ${CYAN}source $ENV_NAME/bin/activate${NC}"
        fi
        echo '    zotero-paper-report --collection "名称"'
    fi
    echo ""
    echo -e "  ${BOLD}To use in Claude Code:${NC}"
    echo -e "    ${CYAN}/zotero-paper-report${NC} 帮我为XX论文生成文献报告"
    echo ""
    echo -e "  ${YELLOW}Note:${NC} Make sure Zotero is running before using zotero-mcp."
else
    echo -e "${RED}✗ Installation completed with $FAIL warning(s).${NC}"
    echo "  Review the warnings above and re-run if needed."
    exit 1
fi
