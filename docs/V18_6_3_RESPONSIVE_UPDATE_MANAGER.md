# IronPanel v18.6.3

This release fixes two operational issues:

1. **Responsive UI**: the admin panel now uses a mobile drawer sidebar, safer grid breakpoints, table overflow guards, and mobile-friendly actions/forms.
2. **GitHub Update Manager**: upgrades are launched with `systemd-run` as `ironpanel-github-upgrade.service`, so the process survives `systemctl restart ironpanel` during the upgrade.

The public subscription page was also redesigned as v4 with an animated glass/aurora layout and better mobile import cards.
