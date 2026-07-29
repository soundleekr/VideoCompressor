# AI File Operation Rule (Prevent Popups)

**Trigger**: This rule must be followed whenever you need to edit, read, copy, or manipulate files in this project.

**Action**:
1. You MUST NOT use `run_command` (e.g., `python -c`, `Copy-Item`, `sed`, `cat`) for editing or copying files. Doing so triggers a mandatory and disruptive security popup for the user.
2. Instead, you MUST use your native file manipulation tools:
   - `write_to_file`
   - `replace_file_content`
   - `multi_replace_file_content`
3. Reserve `run_command` strictly for testing the final GUI application or running necessary builds where terminal output is unavoidable.

By adhering to this, you will provide a seamless and interruption-free experience for the user.
