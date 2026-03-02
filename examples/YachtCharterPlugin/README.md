# SailScanner Yacht Charters Plugin

A WordPress plugin for creating rich Yacht Charter location pages with ACF fields, Kadence-compatible shortcodes, Leaflet maps, and Open-Meteo weather integration.

## Features

✅ Custom Post Type: `yacht_charter` with full archive support  
✅ 18 ACF Field Groups covering all content requirements  
✅ 16+ Shortcodes for flexible page building  
✅ Leaflet Maps with GeoJSON support  
✅ Open-Meteo weather integration with caching  
✅ Mobile-responsive, modern design  
✅ JSON-LD schema markup (FAQs, breadcrumbs, TouristTrip)  
✅ Admin columns and filters  
✅ WooCommerce taxonomy integration for regions/countries  

## Installation

### Method 1: As MU Plugin (Recommended for SailScanner)

**Must-Use plugins are automatically loaded and cannot be deactivated.**

1. Upload `YachtCharterPlugin` folder to `/wp-content/mu-plugins/`
2. Upload `yacht-charter-loader.php` to `/wp-content/mu-plugins/` (root)
3. Verify in Admin > Plugins > Must-Use
4. **No activation needed** - automatically active!
5. Visit Settings > Permalinks and click "Save" to flush rewrite rules

**Final structure:**
```
/wp-content/mu-plugins/
  ├── yacht-charter-loader.php
  └── YachtCharterPlugin/
      ├── sailscanner-yacht-charters.php
      └── [all other files]
```

### Method 2: As Regular Plugin (Alternative)

1. Upload the `YachtCharterPlugin` folder to `/wp-content/plugins/`
2. Activate the plugin through the 'Plugins' menu in WordPress
3. Ensure Advanced Custom Fields Pro is installed and active
4. Visit Settings > Permalinks and click "Save" to flush rewrite rules
5. You'll see a new "Yacht Charters" menu item in the admin sidebar

## Requirements

- WordPress 5.8+
- PHP 7.4+
- Advanced Custom Fields Pro 5.11+
- Kadence Theme (recommended, but works with any theme)
- WooCommerce (optional, for taxonomy integration)

## Post Type: Yacht Charter

**URL Structure:**
- Archive: `/yacht-charters/`
- Singles: `/yacht-charters/mallorca/`, `/yacht-charters/bvi/`, etc.

**Slug:** `yacht_charter`  
**Supports:** Title, Editor, Thumbnail, Excerpt, Revisions  
**Taxonomy:** `product_cat` (WooCommerce categories for regions/countries/islands)

## ACF Field Groups

### 1. Page Meta
- Location name, slug, coordinates
- Region/Country/Island taxonomies
- SEO overrides (canonical, meta title/description, noindex)

### 2. Hero Section
- Headline, subheadline, media (image/video)
- Primary/secondary CTAs with target options

### 3. Value Proposition (USPs)
- Repeater: 3-6 USP cards with icon, title, caption

### 4. Intro (SEO Block)
- WYSIWYG intro content (150-250 words)
- Optional ToC toggle

### 5. Destination Highlights
- Source: Manual cards OR pull from Itinerary CPT
- Card fields: title, image, summary, anchor

### 6. Featured Itinerary
- Post object reference to Itineraries CPT
- Custom title/summary overrides

### 7. Charter Types
- Checkbox: bareboat, skippered, catamaran, crewed luxury, gulet, by cabin
- Benefits repeater per type

### 8. Interactive Map
- Source: from featured itinerary, manual GeoJSON, or none
- Height, controls, theme options

### 9. Weather (Open-Meteo)
- Enable toggle, lat/lon (defaults to page meta)
- Range: current, 7 days, 14 days
- Cache TTL (default 180 minutes)

### 10. Pricing Guide
- Repeater: season, bareboat/catamaran/crewed prices
- Notes and currency code

### 11. How It Works
- Process steps repeater (3-5 steps)

### 12. Why Book With Us
- WYSIWYG content
- Trust badges gallery

### 13. Reviews
- Mode: Trustpilot Custom V1 or None
- Headline, star score, CTA fields

### 14. Lead Capture Form
- Position selector, shortcode field
- Sticky desktop toggle, mobile behavior

### 15. FAQs
- Repeater (4-8 FAQs)
- FAQ schema toggle

### 16. Related Content
- Guides: by categories or manual selection
- Itineraries: by categories or manual selection
- Auto-excludes featured itinerary

### 17. Footer CTA
- Heading, subtext, button label/target

### 18. Safety & Legal (V2)
- WYSIWYG content
- Document downloads repeater

## Shortcodes Reference

### Hero & Introduction

**`[ssyc_hero]`**  
Renders the hero section with headline, subheadline, background image, and CTAs.

**`[ssyc_usps]`**  
Displays value proposition USP cards in a responsive grid.

**`[ssyc_intro]`**  
Outputs the SEO intro block with optional table of contents.

### Content Sections

**`[ssyc_highlights]`**  
Displays destination highlight cards (manual or from itinerary).

**`[ssyc_featured_itinerary]`**  
Shows the featured itinerary card with image, title, summary, and CTA.

**`[ssyc_charter_types]`**  
Renders charter type cards with benefits lists.

### Interactive Elements

**`[ssyc_map]`**  
Displays an interactive Leaflet map with GeoJSON route and markers.

**`[ssyc_weather]`**  
Shows current weather data from Open-Meteo API.

### Information Sections

**`[ssyc_pricing]`**  
Renders pricing table with seasonal rates and notes.

**`[ssyc_process]`**  
Displays "How It Works" process steps.

**`[ssyc_why_us]`**  
Shows "Why Book With Us" content and trust badges.

**`[ssyc_reviews]`**  
Displays Trustpilot review banner with stars and CTA.

**`[ssyc_faqs]`**  
Renders FAQ accordion with schema markup.

### Related Content

**`[ssyc_related_guides]`**  
Shows related guides grid (by categories or manual selection).

**`[ssyc_related_itineraries]`**  
Shows related itineraries grid (excludes featured itinerary).

### CTAs & Forms

**`[ssyc_footer_cta]`**  
Displays footer CTA banner with heading and button.

**`[ssyc_lead_form]`**  
Wrapper for the existing `[sailscanner_lead_form]` shortcode.

## Usage Examples

### Building a Page with Kadence

1. Create a new Yacht Charter post
2. Fill in all ACF field groups
3. In the content editor or Kadence blocks, add shortcodes:

```
[ssyc_hero]

[ssyc_weather]

[ssyc_usps]

[ssyc_intro]

[ssyc_highlights]

[ssyc_featured_itinerary]

[ssyc_map]

[ssyc_charter_types]

[ssyc_pricing]

[ssyc_process]

[ssyc_why_us]

[ssyc_reviews]

[ssyc_lead_form]

[ssyc_faqs]

[ssyc_related_itineraries]

[ssyc_related_guides]

[ssyc_footer_cta]
```

### Using Custom Template

Copy `templates/single-yacht_charter.php` to your theme's root directory and customize as needed.

## Map Configuration

The plugin supports Leaflet maps with GeoJSON data.

**GeoJSON Format:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "name": "Route" },
      "geometry": {
        "type": "LineString",
        "coordinates": [[lon, lat], [lon, lat], ...]
      }
    },
    {
      "type": "Feature",
      "properties": { "label": "Mallorca", "index": 0 },
      "geometry": {
        "type": "Point",
        "coordinates": [lon, lat]
      }
    }
  ]
}
```

**Map Sources:**
1. **From Featured Itinerary**: Automatically pulls GeoJSON from linked itinerary
2. **Manual GeoJSON**: Paste custom GeoJSON in the field
3. **None**: No map displayed

## Weather Integration

Uses Open-Meteo API (no API key required) to fetch current weather data.

**Features:**
- Temperature (°C)
- Wind speed (knots, converted from km/h)
- Wind direction (cardinal)
- Caching via WordPress transients (default 180 minutes)
- Fallback coordinates from page meta

**Cache Management:**  
Transients are stored as `ssyc_wx_{md5(lat,lon)}` and automatically expire.

## Admin Features

**Custom Columns:**
- Location (from charter_location_name)
- Region (from product_cat taxonomy)
- Featured (has featured itinerary?)

**Filters:**
- Filter by Region (product_cat taxonomy dropdown)

**Sortable:**
- Location column sorts by charter_location_name

## Schema Markup (JSON-LD)

The plugin automatically outputs structured data:

1. **BreadcrumbList**: Home → Yacht Charters → [Location]
2. **TouristTrip + Place**: Location name, coordinates, pricing offers
3. **FAQPage**: From FAQs repeater (if schema enabled)

**Rank Math Integration:**  
The plugin removes Rank Math's JSON-LD on yacht_charter pages to avoid duplicates.

## Styling & Customization

**CSS Variables:**  
The plugin respects Kadence theme variables:
- `--global-palette1` (primary color, default #0ea5e9)
- `--global-palette2` (hover color, default #0284c7)

**Custom Styles:**  
Add custom CSS in your theme or via Customizer:

```css
.ssyc-hero {
  min-height: 600px;
}

.ssyc-btn-primary {
  background: #yourcolor;
}
```

## File Structure

```
YachtCharterPlugin/
├── sailscanner-yacht-charters.php    # Main plugin file
├── includes/
│   ├── acf-fields.php                # All 18 ACF field groups
│   ├── shortcodes.php                # All shortcode functions
│   ├── admin.php                     # Admin columns & filters
│   ├── schema.php                    # JSON-LD schema markup
│   └── styles.php                    # Inline CSS
├── assets/
│   └── js/
│       └── ssyc.js                   # Frontend JS (maps, FAQs)
├── templates/
│   └── single-yacht_charter.php      # Optional template
├── Docs and Examples/
│   ├── brief.md                      # Original brief
│   ├── IMPLEMENTATION_PLAN.md        # Implementation plan
│   └── Itineraries_Plugin/           # Reference plugin
└── README.md                         # This file
```

## Developer Notes

### Hooks & Filters

**Custom Actions:**
```php
// Example: Add custom content after hero
add_action('ssyc_after_hero', function($post_id){
  echo '<div class="custom-content">...</div>';
});
```

**Custom Filters:**
```php
// Example: Modify weather cache TTL
add_filter('ssyc_weather_cache_ttl', function($ttl, $post_id){
  return 240; // 4 hours
}, 10, 2);
```

### Helper Functions

**`ssyc_get($key, $post_id = null)`**  
Get ACF field value with fallback to post meta.

**`ssyc_svg($name, $color = '#12305c', $size = 18)`**  
Generate Material Symbols Sharp icons.

**`ssyc_render_stars($rating)`**  
Render star rating with fractional fill.

**`ssyc_fetch_weather($post_id)`**  
Fetch and cache weather data from Open-Meteo.

## Troubleshooting

### Maps not showing?
1. Check browser console for JavaScript errors
2. Ensure Leaflet CSS/JS are loading (check Network tab)
3. Verify GeoJSON is valid JSON format
4. Add `?ssyc_debug=1` to URL for debug logs

### Shortcodes not rendering?
1. Ensure post type is `yacht_charter`
2. Check ACF fields are filled in
3. Verify shortcode names (all start with `ssyc_`)

### Weather not updating?
1. Check coordinates are valid (geo_lat, geo_lon)
2. Clear WordPress transients or wait for cache TTL
3. Test API directly: `https://api.open-meteo.com/v1/forecast?latitude=39.5&longitude=2.7&current=temperature_2m`

### Permalink 404 errors?
1. Go to Settings > Permalinks
2. Click "Save Changes" (flushes rewrite rules)
3. Test archive: `/yacht-charters/`

## Support & Development

**Version:** 1.0.0  
**Author:** SailScanner  
**Documentation:** See `Docs and Examples/` folder  

## Changelog

### 1.0.0 - 2024
- Initial release
- 18 ACF field groups
- 16+ shortcodes
- Leaflet map integration
- Open-Meteo weather integration
- JSON-LD schema markup
- Admin columns and filters
- Mobile-responsive design

## License

Proprietary - SailScanner Ltd.

