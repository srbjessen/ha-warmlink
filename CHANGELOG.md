# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Additional language translations
- More dashboard examples
- Automation templates
- Enhanced diagnostics

## [63.0] - 2026-01-24

### Added
- Initial public release on GitHub
- Professional Amber Waves logo (256x256 + 512x512 hDPI)
- Comprehensive documentation
- Dashboard examples
- HACS support
- GitHub issue templates
- Contributing guidelines

### Fixed
- Logo display preparation for Home Assistant brands repository

## [60.0] - 2026-01-24

### Added
- Local value caching to prevent "unavailable" states during updates
- Enhanced error handling that preserves old data when API calls fail
- Improved stability during network issues

### Changed
- Sensors now cache their last known value
- `available` property logic improved
- Better handling of temporary API failures

### Fixed
- Sensors no longer show "unavailable" during the 2-second update window
- Statistics and graphs remain intact during updates
- Long-term statistics tracking maintained

### Technical Details
- Added `_cached_value` and `_cached_attrs` to sensor entities
- Modified `coordinator.py` to preserve old data on API failures
- Improved `available` property to check cached values

## [58.0] - 2026-01-23

### Added
- Expanded from 207 to 350 sensor codes
- Multi-language support (English + Danish)
- Comprehensive translations for all sensors
- Enhanced logging system for debugging
- Automatic discovery of new sensor codes
- Missing sensor tracking and reporting

### Changed
- Improved code organization and structure
- Better error messages for troubleshooting
- Enhanced API communication efficiency

### Fixed
- Token refresh handling improvements
- Batch API call optimization

## [29.0] - 2026-01-21

### Added
- Initial working version
- Basic sensor support (207 codes)
- Configuration flow for easy setup
- Device info integration
- Basic English translations
- Automatic token refresh

### Known Issues
- Sensors briefly show "unavailable" during updates (fixed in v60+)
- Manual reload occasionally needed (fixed in v60+)

---

## Upgrade Notes

### Upgrading to v63+
No special steps required if upgrading from v60-v62. Just update via HACS or manually.

### Upgrading to v60+

**Important**: Value caching changes require complete reinstallation:

1. **Delete** the WarmLink integration from Home Assistant
2. **Restart** Home Assistant  
3. **Re-add** the integration with your credentials

Your historical data will be preserved in the database.

### Upgrading to v58+

New sensor codes added. To see them:
- Option 1: Delete and re-add the integration (recommended)
- Option 2: Just restart Home Assistant (new codes will appear gradually)

---

## Version Numbering

This project uses [Semantic Versioning](https://semver.org/):
- **Major version** (X.0): Breaking changes requiring reinstallation
- **Minor version** (X.Y): New features, backward compatible  
- **Patch version** (X.Y.Z): Bug fixes only

Current version follows Home Assistant custom integration standards with major.minor format (e.g., 63.0).

---

## See Also

- [Installation Guide](docs/installation.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [GitHub Releases](https://github.com/srbjessen/ha-warmlink/releases)
