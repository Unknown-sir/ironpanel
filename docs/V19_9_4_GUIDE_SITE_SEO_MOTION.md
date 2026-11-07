# 19.9.4 - Guide Site SEO & Motion Refresh

This release refreshes the IronPanel public guide website bundled with LicensePanel.

## Changes

- Removed the LicensePanel-installation paragraph from the hero section.
- Added a more modern Matrix/aurora visual language aligned with IronPanel login styling.
- Added responsive feature cards, timeline, protocol accordions, node/relay guide, command cards and FAQ.
- Added SEO metadata targeted for IronPanel and Persian search queries.
- Added Open Graph, Twitter card, canonical URL, SoftwareApplication JSON-LD and FAQPage JSON-LD.
- Installer now generates `robots.txt`, `sitemap.xml` and `manifest.webmanifest`.
- Nginx config includes improved static cache and basic security headers.

## Manual reinstall

```bash
sudo bash /opt/license-panel/scripts/install_guide_site.sh \
  --domain help.example.com \
  --email admin@example.com \
  --support-id @Ironpanel_support \
  --github-url https://github.com/Unknown-sir/ironpanel
```
