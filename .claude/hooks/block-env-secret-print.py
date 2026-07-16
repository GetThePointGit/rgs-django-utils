#!/usr/bin/env python3
"""
PreToolUse hook to block Bash commands that would print raw secret values from .env files.
Reads JSON from stdin, writes JSON to stdout, blocks with a deny decision if matching.
"""
import sys
import json
import re

def is_blocked(command: str) -> tuple[bool, str]:
    """Check if a Bash command should be blocked. Returns (should_block, reason)."""

    # Exception: whitelisted env files (templates/examples contain no real secrets by convention)
    if ".env.template" in command or ".env.example" in command:
        return False, ""

    # Check 1: Does the command reference an env file?
    if not re.search(r'\.env(\.\w+)?\b', command):
        return False, ""

    # Check 2: Is it a dump/print operation on the file?
    dump_patterns = [
        r'\bcat\s+',
        r'\bless\s+',
        r'\bmore\s+',
        r'\bhead\s+',
        r'\btail\s+',
        r'\bstrings\s+',
        r'\b(e?)grep\b(?!\s+-[clqL])',  # grep/egrep but not with -c/-l/-q (count/list only)
        r'\bprintenv\b',
        r'\benv\b(?!\s+-)',  # bare env, not env -i or env -u
        r'\bexport\s+-p\b',
        r'\bdocker\s+inspect.*\s+env',
        r'\bpython\d*\s+-c.*open\(',
        r'\bnode\s+-e.*open\(',
    ]
    is_dump = any(re.search(p, command, re.IGNORECASE) for p in dump_patterns)
    if not is_dump:
        return False, ""

    # Check 3: Is a sensitive key name involved?
    sensitive_patterns = [
        r'SECRET',
        r'PASSWORD',
        r'TOKEN',
        r'_KEY',
        r'ADMIN',  # catches HASURA_GRAPHQL_ADMIN_SECRET etc.
    ]
    has_sensitive_key = any(re.search(p, command, re.IGNORECASE) for p in sensitive_patterns)

    # Also block bare file dumps (cat .env without filters)
    is_bare_env_dump = bool(re.search(r'\bcat\s+[\'"]?\.env[\'"]?\s*(?:\||$|\s)', command))

    if not (has_sensitive_key or is_bare_env_dump):
        return False, ""

    # Check 4: Is there existing redaction/hashing in the pipeline?
    redaction_patterns = [
        r'\bsed\b.*\*{2,}',  # sed with **** replacement
        r'\b(sha256sum|shasum|md5sum|md5|openssl\s+dgst|cksum)\b',  # hashing
        r'\bwc\s+-[lc]',  # count only (line/char)
        r'grep\s+-c\b',  # grep count only
    ]
    has_redaction = any(re.search(p, command, re.IGNORECASE) for p in redaction_patterns)
    if has_redaction:
        return False, ""

    # If all checks passed, block it
    reason = (
        "Dit commando zou een rauwe secret-waarde uit een .env-bestand naar stdout printen, "
        "wat als tool-resultaat naar het model (en dus Anthropic) gaat. "
        "Vergelijk secrets via checksum (bv. sha256sum) i.p.v. de waarde te printen, "
        "of vraag de gebruiker expliciet om bevestiging als je 'm echt moet tonen."
    )
    return True, reason

def main():
    try:
        # Read hook input from stdin
        payload = json.load(sys.stdin)

        # Extract the command from the Bash tool input
        command = payload.get("tool_input", {}).get("command", "")

        # Check if blocked
        should_block, reason = is_blocked(command)

        if should_block:
            # Output deny decision
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason
                }
            }
            print(json.dumps(output))
            sys.exit(0)
        else:
            # No output = implicit allow
            sys.exit(0)

    except Exception:
        # On error, allow the command silently
        # (don't crash the hook, just let it through)
        sys.exit(0)

if __name__ == "__main__":
    main()
