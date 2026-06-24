# Changelog

All notable changes to this project are documented here.

This project uses the Keep a Changelog format. Versions 0.8.0 and earlier predate this changelog.

## [0.9.0] - 2026-06-23

### Added

- Tool-level hub config (`zentaizo config set|get|unset hub`) and the `--zentaizo`/`-Z` routing flag so a spoke workspace files efforts/docs into a configured hub workspace.

### Changed

- Robust global-config IO (`CliError` on corrupt/non-object JSON; atomic write).
