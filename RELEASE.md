# Launch Notes

## 2.4.0 (9/2/2025)

### New Features
- Added ability to test ODBC connections on Settings page.
- Added ability to undo file deletions from upload list on Upload page.
- Added preinstalled PostgreSQL and MariaDB database drivers.
- Sample ODBC connection strings are now provided when adding a new database.
- Added support for GPT-5 model.

### Changed
- In the results table on the Data Explorer page, RowIDs returned from queries now show the properties of the node or edge represented by the ID instead of the ID.
- In the results table on the Data Explorer page, paths returned from queries now show a list of the properties of the node or edge represented by the ID instead of a list of IDs.
- In the results graph on the Data Explorer page, edges returned from queries as RowIDs are now displayed only once on the graph.
- The results table on the Data Explorer page now shows part of the data with a scrollbar to improve performance.  The table can also be resized.
- Only the sensitive fields of an ODBC connection string are masked now.
- The dashboard schema widget and Datasets page now show a list of demo datasets to load when no datasets are loaded.
- Multi-line input boxes now support keyboard shortcuts.  Enter submits.  Ctrl-Enter, Cmd-Enter, Shift-Enter, and Alt-Enter all add a newline.
- All times are now shown in the browser's local time.
- Copy buttons no longer steal focus on click on some inputs; the active input remains focused for all copy buttons.
- All copy buttons now show a temporary checkmark with text to confirm success, instead of some displaying a toast notification.
- Pages now update automatically when demo data finishes loading.

### Fixed
- Fixed bug where occasionally Mission Control thought a user was logged in even after logout.
- Fixed demo data loading so multiple users on the same system can load the same demo data set.
- Fixed bug where demo data load failures weren't shown to the user.
- Fixed bug where demo data failed if the load took more than 30 seconds.
- Fixed issues when running the containerized xGT with SELinux.
- Fixed bug where occasionally a user would be incorrectly logged out due to an invalid timeout between Mission Control and the xGT server.
- Fixed an issue where graphs could be generated with empty schemas.
- Fixed an issue where the history button did not appear clickable for some inputs.
- Fixed a bug in error handling logic where valid error messages were lost and replaced with NameError (undefined symbol).
- Fixed an issue where schema graphs could randomly select nodes or edges while dragging the display.
- Fixed an issue where loading multiple demo samples simultaneously could cause load failures.
- Fixed a bug where dragging a single node on the schema graph caused it to snap back to its original position.
- Fixed a bug in the schema graph where, after dragging, hovering over a node or edge showed the overlay popup at the mouse’s previous position instead of the current one.


## 2.3.0 (6/9/2025)

### New Features
- Added support for newer ChatGPT and Anthropic LLM models.
- Added tour capability along with login and dashboard tours.
- Added support for editing and renaming bookmarks and folders, updating bookmark content and folder assignments, creating custom folders, and reorganizing bookmarks via drag-and-drop.
- Added netflow demo dataset.

### Changed
- Improved column type inferencing of CSV files.
- Improved syntax highlighting of Cypher.
- The Mission Control launch notes are now available even when logged out.
- Changed the default host directories for configuration, data, and log files to be in the host user's directory to support multiple users on the same system.

### Fixed
- Fixed some bugs that occurred when entering LLM keys on the settings page.
- Fixed bug where the columns from an LLM response weren't mapped correctly to the data columns when generating an SQL query.
- Fixed bug where an ignored license expiration banner never came back.


## 2.2.2 (4/23/2025)

### New Features
- Added warning pop-up to notify users of upcoming license expiration.
- Added button to load demo data.

### Changed
- The answer graph now shows multiple edges between the same two nodes.
- The answer graph can now visualize queries that use aliases of properties.
- The number of rows for the job is now a column on the jobs page.
- Added millisecond resolution to the reported query and job times.

### Fixed
- Fixed answer graph visualization to distinguish nodes by both frame type and key value to prevent incorrect merges across node types with overlapping keys.
- Fixed CSV inference failure caused by unnormalized Windows line endings by standardizing line breaks before parsing.
- Fixed a bug where the answer graph visualization could hang when the same label was used multiple times or when properties were aliased.


## 2.2.1 (4/9/2025)

### Changed
- Answer graph and dynamic visualization now stay on and update when the page or rows per page is updated in the results table.
- Improved some descriptions to make it clear the answer graph and dynamic display on the data explorer page use displayed result data only.
- Starting with 2.2.1, Mission Control can be compatible with older or newer versions of the xGT server.

### Fixed
- Fixed a bug where null edges or nodes sometimes showed up in a graph visualization.
- Fixed a bug where the wrong query was sometimes put in the query box on the data explorer page when navigating from the jobs page by clicking on viewing the job data.


## 2.2.0 (3/31/2025)

### New Features
- Added a bookmark feature to the histories to save frequently used questions and queries.
- Added a cancel button to the job status box on the data explorer page.
- Added a help button with documentation and architecture diagrams.
- Added launch notes for Mission Control and a link to the xGT launch notes.

### Changed
- Simplified the top header bar, including moving the server info to the settings page.
- Upgraded Claude to use 3.7.
- The Cypher returned from asking an LLM a question is now put directly in the query box.
- Reduced polling interval on status of running query to 1 second to know result more quickly.
- The query status box on the data explorer page now supports all job status types.
- Improved performance of interacting with histories.
- Improved error reporting from LLMs.
- The chat feature is no longer experimental.
- Improved the errors returned to the user when the LLM generates an invalid schema.
- Removed Logs page as it was basically a duplication of the Jobs page.

### Fixed
- Fixed a bug where the wrong properties were sometimes displayed in the answer graph when multiple nodes or edges from the same frame were given in the RETURN statement.
- Fixed an issue where Mistral results were being interpreted incorrectly and causing errors.
- Fixed a bug where the graph creation button became permanently disabled after a failed attempt to create a graph.
