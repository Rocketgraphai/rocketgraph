# Launch Notes

## 2.2.2 (4/23/2025)

### New Features
- Added warning popup to notify users of upcoming license expiration.
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
- Fixed a bug where null edges or vertices sometimes showed up in a graph visualization.
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
- Fixed a bug where the wrong properties were sometimes displayed in the answer graph when multiple vertices or edges from the same frame were given in the RETURN statement.
- Fixed an issue where Mistral results were being interpreted incorrectly and causing errors.
- Fixed a bug where the graph creation button became permanently disabled after a failed attempt to create a graph.
