Proceed with the next runtime stabilization task.

Before making changes, review the Existing workflow.

I agree that automatic detection should not leave the user stuck.

Requirements:

1. Automatic detection should still execute on first file/folder selection.

2. If automatic detection succeeds:
   - Continue normally.

3. If automatic detection fails:
   - Display a clear error message explaining why.
   - Keep the uploaded file/folder in the current session.
   - Provide a "Retry Detection" button.
   - Provide a "Start Detection Manually" button.
   - Do NOT require the user to reselect the file/folder.

4. Do not rerun parsing or preview unless the user explicitly retries.

5. Preserve the current architecture.

6. Make the smallest possible runtime fix.

After implementing, stop and wait for my testing.
