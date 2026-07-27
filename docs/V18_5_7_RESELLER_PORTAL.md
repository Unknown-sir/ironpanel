# IronPanel v18.5.7 - Reseller Portal Link & Quota Controls

This release fixes reseller panel addressing and management.

## Added

- Dedicated reseller login URL generation in `/resellers`.
- Supported URLs: `/r/<panel_path>` and `/reseller/<panel_path>`.
- Editable reseller user limit.
- Editable reseller traffic allocation quota in GB.
- Admin suspend/resume for reseller panel access.
- Quota enforcement when reseller creates users or increases a user traffic limit.

## Notes

A disabled reseller cannot log in. Existing VPN users created by that reseller are not automatically deleted; this option only stops the reseller panel login.
