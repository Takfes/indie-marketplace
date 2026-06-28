#!/bin/bash
# Skill Downloader - Bash fallback version
# This script downloads specific folders from GitHub repos using sparse-checkout
# Use when Python is not available

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️ ${1}${NC}"
}

log_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  ${1}${NC}"
}

log_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

# Cleanup on exit
cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        log_info "Removing temporary workspace..."
        rm -rf "$TEMP_DIR"
        log_success "Temporary workspace cleaned up"
    fi
}

trap cleanup EXIT

# Main process
main() {
    # Capture the project root immediately, before any `cd` changes our location.
    # All relative destination paths (e.g. .claude/skills) are resolved against
    # this directory, so the result is independent of where git operations move us.
    PROJECT_DIR=$(pwd)

    echo ""
    echo "============================================================"
    echo "🎯 Skill Downloader - GitHub Repository Download Utility"
    echo "============================================================"
    echo ""

    # Get repository URL
    log_info "📦 Repository Details"
    echo ""
    read -p "GitHub repository URL (e.g., https://github.com/anthropics/superpowers.git): " REPO_URL

    if [ -z "$REPO_URL" ]; then
        log_error "Repository URL is required"
        return 1
    fi

    # Normalize URL
    if [[ ! "$REPO_URL" == *.git ]]; then
        REPO_URL="${REPO_URL}.git"
    fi

    # Get path in repo
    read -p "Path in repository (e.g., skills/brainstorming): " REPO_PATH

    if [ -z "$REPO_PATH" ]; then
        log_error "Repository path is required"
        return 1
    fi

    # Get branch (optional)
    read -p "Branch name (press Enter for 'main'): " BRANCH
    BRANCH=${BRANCH:-main}

    echo ""

    # Select destination
    log_info "📂 Destination"
    echo ""
    echo "Select destination for downloaded files:"
    echo "  1) .claude/skills       (Default)"
    echo "  2) .gemini/skills"
    echo "  3) .agents/"
    echo "  4) Custom path"
    echo ""
    read -p "Choose [1-4] (default: 1): " DEST_CHOICE
    DEST_CHOICE=${DEST_CHOICE:-1}

    case $DEST_CHOICE in
        1)
            DESTINATION=".claude/skills"
            log_info "Destination: $DESTINATION"
            ;;
        2)
            DESTINATION=".gemini/skills"
            log_info "Destination: $DESTINATION"
            ;;
        3)
            DESTINATION=".agents/"
            log_info "Destination: $DESTINATION"
            ;;
        4)
            read -p "Enter custom destination path: " DESTINATION
            if [ -z "$DESTINATION" ]; then
                log_error "Destination path cannot be empty"
                return 1
            fi
            ;;
        *)
            log_error "Invalid choice: $DEST_CHOICE. Please choose 1-4."
            return 1
            ;;
    esac

    # Resolve to absolute path now, while we're still in PROJECT_DIR.
    # This prevents relative paths (e.g. .claude/skills) from resolving
    # against $TEMP_DIR after the sparse-checkout `cd` below.
    if [[ "$DESTINATION" != /* ]]; then
        DESTINATION="$PROJECT_DIR/$DESTINATION"
    fi
    log_info "Resolved destination: $DESTINATION"

    echo ""

    # Validate repository
    log_info "🔍 Validating repository..."

    if ! git ls-remote --heads "$REPO_URL" "$BRANCH" > /dev/null 2>&1; then
        log_error "Repository not found or not accessible: $REPO_URL"
        return 1
    fi

    log_success "Repository accessible"

    echo ""

    # Create temporary workspace
    log_info "🔧 Setting up temporary workspace..."

    TEMP_DIR=$(mktemp -d -t skill_download_XXXXXX)
    log_success "Workspace created: $TEMP_DIR"

    echo ""

    # Initialize sparse checkout
    log_info "📥 Initializing sparse checkout..."

    cd "$TEMP_DIR"
    git init > /dev/null 2>&1
    git remote add origin "$REPO_URL"
    git config core.sparseCheckout true

    # Configure sparse-checkout file
    mkdir -p .git/info
    echo "${REPO_PATH}/*" >> .git/info/sparse-checkout

    log_success "Sparse checkout configured"

    echo ""

    # Pull content
    log_info "📡 Pulling $REPO_PATH from $BRANCH..."

    if ! git pull origin "$BRANCH" > /dev/null 2>&1; then
        log_error "Failed to pull from repository. Check if path exists and branch is correct."
        cd - > /dev/null
        return 1
    fi

    log_success "Content pulled successfully"

    echo ""

    # Extract and move
    log_info "📦 Extracting content..."

    SOURCE_PATH="$TEMP_DIR/$REPO_PATH"
    if [ ! -d "$SOURCE_PATH" ]; then
        log_error "Extracted path not found: $SOURCE_PATH"
        cd - > /dev/null
        return 1
    fi

    # Create destination if needed
    mkdir -p "$DESTINATION"

    # Get folder name
    FOLDER_NAME=$(basename "$SOURCE_PATH")
    FINAL_DEST="$DESTINATION/$FOLDER_NAME"

    # Check if destination already exists
    if [ -d "$FINAL_DEST" ]; then
        log_warning "Destination already exists: $FINAL_DEST"
        read -p "Overwrite? (y/n) [n]: " OVERWRITE
        if [ "$OVERWRITE" != "y" ]; then
            log_info "Download cancelled"
            cd - > /dev/null
            return 1
        fi
        rm -rf "$FINAL_DEST"
        log_info "Removed existing: $FINAL_DEST"
    fi

    # Copy content
    cp -r "$SOURCE_PATH" "$FINAL_DEST"
    log_success "Extracted to: $FINAL_DEST"

    cd - > /dev/null

    echo ""

    # Clean git artifacts
    log_info "🧹 Cleaning git artifacts..."

    REMOVED_COUNT=0

    # Remove .git directories
    find "$FINAL_DEST" -type d -name ".git" -exec rm -rf {} + 2>/dev/null && ((REMOVED_COUNT++)) || true

    # Remove git-related files
    for pattern in ".gitignore" ".gitattributes" ".gitmodules" ".github" ".gitkeep"; do
        find "$FINAL_DEST" -name "$pattern" -exec rm -rf {} + 2>/dev/null && ((REMOVED_COUNT++)) || true
    done

    if [ $REMOVED_COUNT -gt 0 ]; then
        log_success "Removed $REMOVED_COUNT git-related items"
    else
        log_info "No git artifacts found (expected for clean content)"
    fi

    echo ""

    # Clean empty directories
    log_info "🧹 Cleaning empty directories..."

    find "$FINAL_DEST" -type d -empty -delete 2>/dev/null || true
    log_info "Empty directories cleaned"

    echo ""

    # Success summary
    echo "============================================================"
    log_success "Download completed successfully!"
    echo "============================================================"
    log_info "Content available at: $FINAL_DEST"
    echo ""

    return 0
}

main "$@"
exit $?
