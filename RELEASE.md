# Launch Notes

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
- Removed Logs tab as it was basically a duplication of the Jobs tab.

### Fixed
- Fixed a bug where the wrong properties were sometimes displayed in the answer graph when multiple vertices or edges from the same frame were given in the RETURN statement.
- Fixed an issue where Mistral results were being interpreted incorrectly and causing errors.
- Fixed a bug where the graph creation button became permanently disabled after a failed attempt to create a graph.
