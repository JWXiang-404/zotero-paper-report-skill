#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# zotero-paper-report-skill — One-Click Installer
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SKILL_NAME="zotero-paper-report"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT="claude"

# --- Helper functions ---

print_ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
print_err()  { echo -e "  ${RED}✗${NC} $1"; }
print_info() { echo -e "  ${CYAN}→${NC} $1"; }
banner()     { echo -e "\n${CYAN}===${NC} $1 ${CYAN}===${NC}"; }

usage() {
    cat <<EOF
Usage: install.sh [--agent claude|opencode] [--help]

Install the zotero-paper-report skill and its vendored dependencies.

Options:
  --agent <name>   Target coding agent (default: claude)
                   Currently supported: claude
                   Reserved for future: opencode
  --help           Show this help message

Examples:
  ./install.sh                    # Install for Claude Code
  ./install.sh --agent claude     # Same as above
EOF
    exit 0
}

# --- Parse arguments ---

while [[ $# -gt 0 ]]; do
    case "$1" in
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

SKILLS_DIR="$HOME/.claude/skills"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

# ============================================================
# Step 1: Check prerequisites
# ============================================================
banner "Step 1/4: Checking prerequisites"

MISSING=0

# Claude CLI
if command -v "$CLAUDE_BIN" &>/dev/null; then
    print_ok "claude CLI found"
else
    print_err "claude CLI not found"
    print_info "Install Claude Code: https://docs.anthropic.com/en/docs/claude-code"
    MISSING=$((MISSING + 1))
fi

# npm
if command -v npm &>/dev/null; then
    print_ok "npm found"
else
    print_err "npm not found (required for zotero-mcp)"
    print_info "Install Node.js: https://nodejs.org/"
    MISSING=$((MISSING + 1))
fi

# zotero-mcp
ZOTERO_MCP_FOUND=false
if command -v npx &>/dev/null && npx --yes zotero-mcp --version &>/dev/null 2>&1; then
    ZOTERO_MCP_FOUND=true
elif [ -d "$HOME/.zotero-mcp" ] || [ -f "$HOME/.config/zotero-mcp/config.json" ] 2>/dev/null; then
    ZOTERO_MCP_FOUND=true
fi
if $ZOTERO_MCP_FOUND; then
    print_ok "zotero-mcp detected"
else
    print_warn "zotero-mcp may not be installed/configured"
    print_info "Install guide: https://github.com/cookjohn/zotero-mcp/blob/main/README-zh.md"
fi

# claude-scientific-writer plugin
SW_SKILL="$SKILLS_DIR/scientific-writing/SKILL.md"
if [ -f "$SW_SKILL" ]; then
    print_ok "scientific-writing skill found"
else
    print_warn "scientific-writing skill not found"
    print_info "Install via Claude Code plugin:"
    print_info "  https://github.com/K-Dense-AI/claude-scientific-writer#-use-as-a-claude-code-plugin-recommended"
fi

echo ""
if [ $MISSING -gt 0 ]; then
    echo -e "${YELLOW}Warning: $MISSING required tool(s) missing. Please install them before using the skill.${NC}"
    echo ""
fi

# ============================================================
# Step 2: Check submodule
# ============================================================
banner "Step 2/4: Checking vendored dependencies"

PDF_SKILL_SRC="$SCRIPT_DIR/3rdparty/anthropics-skills/skills/pdf"

if [ -f "$PDF_SKILL_SRC/SKILL.md" ]; then
    print_ok "pdf skill (vendored)"
else
    print_err "pdf skill submodule not found"
    print_info "Run: git submodule update --init --recursive"
    exit 1
fi

# ============================================================
# Step 3: Install skills
# ============================================================
banner "Step 3/4: Installing skills"

mkdir -p "$SKILLS_DIR"

# Install zotero-paper-report
ZPR_SRC="$SCRIPT_DIR/zotero-paper-report"
ZPR_DST="$SKILLS_DIR/zotero-paper-report"
rm -rf "$ZPR_DST"
cp -r "$ZPR_SRC" "$ZPR_DST"
print_ok "Installed zotero-paper-report -> $ZPR_DST"

# Install pdf skill from 3rdparty
PDF_DST="$SKILLS_DIR/pdf"
rm -rf "$PDF_DST"
cp -r "$PDF_SKILL_SRC" "$PDF_DST"
print_ok "Installed pdf skill       -> $PDF_DST"

# ============================================================
# Step 4: Verify
# ============================================================
banner "Step 4/4: Verifying installation"

FAIL=0

if [ -f "$ZPR_DST/SKILL.md" ]; then
    print_ok "zotero-paper-report/SKILL.md"
else
    print_err "zotero-paper-report/SKILL.md MISSING"
    FAIL=$((FAIL + 1))
fi

if [ -f "$PDF_DST/SKILL.md" ]; then
    print_ok "pdf/SKILL.md"
else
    print_err "pdf/SKILL.md MISSING"
    FAIL=$((FAIL + 1))
fi

# ============================================================
# Summary
# ============================================================
echo ""
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ Installation complete!${NC}"
    echo ""
    echo -e "Usage in Claude Code:"
    echo -e "  ${CYAN}/zotero-paper-report${NC} 帮我为标题包含\"关键词\"的论文生成文献报告"
    echo ""
    echo -e "Quick start: just describe a paper in your Zotero library and ask for a report."
else
    echo -e "${RED}✗ Installation failed with $FAIL error(s).${NC}"
    exit 1
fi
