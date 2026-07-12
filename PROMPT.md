A workflow integration bug still exists after the Workflow Refactoring Sprint.

The architecture is correct, but the implementation is not behaving correctly.

Observed behaviour:

1. Connection Manager successfully connects to the remote datasource.
2. Remote directory is browsed.
3. Files are listed.
4. A file is selected.
5. Raw preview is displayed successfully.
6. DiscoveryResult should now exist.

However, after entering the Discovery phase the UI displays:

"No files found at remote path..."

This should never happen because Discovery must consume the DiscoveryResult already produced by Connection Manager.

=================================================

TASK

Perform a full trace of the workflow.

Connection Manager

↓

Discovery

↓

Configuration Builder

Verify every transition.

=================================================

Specifically verify

• Is DiscoveryResult actually stored in session state?

• Is it copied into ProcessingContext?

• Is ProcessingContext passed into Discovery?

• Is Discovery reading ctx.discovery?

• Is Discovery unnecessarily calling get_file_list()?

• Is Discovery unnecessarily calling datasource.list()?

• Is Discovery rebuilding file paths?

• Is the remote datasource being replaced with a local datasource?

• Is session_state cleared between pages?

• Is the DiscoveryResult path matching logic failing?

=================================================

For every phase produce a trace such as:

Connection Manager
Created DiscoveryResult ✓

Stored in session_state ✓

Copied into ProcessingContext ✓

Discovery
Received ProcessingContext ✓

Received DiscoveryResult ✓

Skipped Detection ✓

Skipped File Enumeration ✓

Skipped Preview Generation ✓

Configuration
Received DiscoveryResult ✓

Used existing metadata ✓

Skipped re-detection ✓

=================================================

If any phase performs duplicate work, remove it.

Discovery should become a confirmation page.

It should NEVER

• enumerate files again
• rediscover file type
• regenerate preview
• rediscover delimiter
• rediscover multiline
• rediscover layouts

unless the user explicitly changes the selected dataset.

=================================================

Also review the UI.

Once a dataset has been selected in Connection Manager, Discovery should not expose controls that imply another file selection unless the user intentionally requests to change the source.

=================================================

Run the complete Playwright suite and regression tests afterwards.

Produce a root-cause report explaining why the duplicate workflow still occurred even after the Workflow Refactoring Sprint.
