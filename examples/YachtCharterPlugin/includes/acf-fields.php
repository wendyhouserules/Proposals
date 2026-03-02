<?php
/**
 * ACF Field Groups for Yacht Charters
 * 18 field groups matching the brief specifications
 */

if ( ! defined('ABSPATH') ) exit;

add_action('acf/init', function(){
  if ( ! function_exists('acf_add_local_field_group') ) return;

  /* ========================================
   * Group 1: Page Meta
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_page_meta',
    'title' => 'Page Meta',
    'fields' => [
      ['key'=>'ssyc_charter_location_name', 'label'=>'Location Name', 'name'=>'charter_location_name', 'type'=>'text', 'instructions'=>'e.g., "Mallorca"'],
      ['key'=>'ssyc_charter_location_slug', 'label'=>'Location Slug', 'name'=>'charter_location_slug', 'type'=>'text', 'instructions'=>'e.g., "mallorca"'],
      ['key'=>'ssyc_geo_lat', 'label'=>'Latitude', 'name'=>'geo_lat', 'type'=>'number', 'step'=>'0.000001'],
      ['key'=>'ssyc_geo_lon', 'label'=>'Longitude', 'name'=>'geo_lon', 'type'=>'number', 'step'=>'0.000001'],
      ['key'=>'ssyc_region_taxonomy', 'label'=>'Region (taxonomy)', 'name'=>'region_taxonomy', 'type'=>'taxonomy', 'taxonomy'=>'product_cat', 'field_type'=>'multi_select', 'return_format'=>'id'],
      ['key'=>'ssyc_country_taxonomy', 'label'=>'Country (taxonomy)', 'name'=>'country_taxonomy', 'type'=>'taxonomy', 'taxonomy'=>'product_cat', 'field_type'=>'select', 'return_format'=>'id'],
      ['key'=>'ssyc_island_taxonomy', 'label'=>'Island (taxonomy)', 'name'=>'island_taxonomy', 'type'=>'taxonomy', 'taxonomy'=>'product_cat', 'field_type'=>'multi_select', 'return_format'=>'id'],
      // Removed: canonical_url, meta_title
      ['key'=>'ssyc_meta_description', 'label'=>'Meta Description (override)', 'name'=>'meta_description', 'type'=>'textarea', 'rows'=>3],
      ['key'=>'ssyc_noindex', 'label'=>'No Index', 'name'=>'noindex', 'type'=>'true_false', 'default_value'=>0],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
    'style' => 'default',
  ]);

  /* ========================================
   * Group 2: Hero (removed)
   * ======================================== */
  // Entire hero group removed

  /* ========================================
   * Group 3: Value Proposition (USPs)
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_usps',
    'title' => 'Value Proposition (USPs)',
    'fields' => [
      [
        'key'=>'ssyc_usps', 'label'=>'USPs', 'name'=>'usps', 'type'=>'repeater', 'min'=>3, 'max'=>6, 'layout'=>'table', 'button_label'=>'Add USP',
        'sub_fields'=>[
          ['key'=>'ssyc_usp_icon', 'label'=>'Icon', 'name'=>'usp_icon', 'type'=>'text', 'instructions'=>'Icon name or image URL'],
          ['key'=>'ssyc_usp_title', 'label'=>'Title', 'name'=>'usp_title', 'type'=>'text'],
          ['key'=>'ssyc_usp_caption', 'label'=>'Caption', 'name'=>'usp_caption', 'type'=>'text'],
        ]
      ],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 4: Intro (SEO Block)
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_intro',
    'title' => 'Intro (SEO Block 1)',
    'fields' => [
      ['key'=>'ssyc_intro_html', 'label'=>'Intro Content', 'name'=>'intro_html', 'type'=>'wysiwyg', 'tabs'=>'all', 'toolbar'=>'basic', 'media_upload'=>1, 'instructions'=>'150-250 words; include one internal link'],
      // Removed: show_toc
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 5: Destination Highlights
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_highlights',
    'title' => 'Destination Highlights (Cards)',
    'fields' => [
      ['key'=>'ssyc_highlights_source', 'label'=>'Highlights Source', 'name'=>'highlights_source', 'type'=>'select', 'choices'=>['manual'=>'Manual','from_itinerary'=>'From Itinerary'], 'default_value'=>'manual', 'ui'=>1],
      [
        'key'=>'ssyc_highlights_cards', 'label'=>'Highlight Cards', 'name'=>'highlights_cards', 'type'=>'repeater', 'min'=>3, 'max'=>8, 'layout'=>'row', 'button_label'=>'Add Highlight',
        'conditional_logic'=>[[['field'=>'ssyc_highlights_source','operator'=>'==','value'=>'manual']]],
        'sub_fields'=>[
          ['key'=>'ssyc_highlight_title', 'label'=>'Title', 'name'=>'highlight_title', 'type'=>'text'],
          ['key'=>'ssyc_highlight_image', 'label'=>'Image', 'name'=>'highlight_image', 'type'=>'image', 'return_format'=>'array'],
          ['key'=>'ssyc_highlight_summary', 'label'=>'Summary', 'name'=>'highlight_summary', 'type'=>'textarea', 'rows'=>3, 'instructions'=>'30-60 words'],
          ['key'=>'ssyc_highlight_anchor_slug', 'label'=>'Anchor Slug', 'name'=>'highlight_anchor_slug', 'type'=>'text'],
        ]
      ],
      ['key'=>'ssyc_highlights_itinerary_ref', 'label'=>'Itinerary Reference', 'name'=>'highlights_itinerary_ref', 'type'=>'post_object', 'post_type'=>['itinerary'], 'return_format'=>'id', 'conditional_logic'=>[[['field'=>'ssyc_highlights_source','operator'=>'==','value'=>'from_itinerary']]]],
      ['key'=>'ssyc_highlights_show_count', 'label'=>'Show Count', 'name'=>'highlights_show_count', 'type'=>'number', 'default_value'=>4, 'min'=>1, 'max'=>8],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 6: Featured Itinerary
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_featured_itinerary',
    'title' => 'Featured Itinerary',
    'fields' => [
      ['key'=>'ssyc_featured_itinerary', 'label'=>'Featured Itinerary', 'name'=>'featured_itinerary', 'type'=>'post_object', 'post_type'=>['itinerary'], 'return_format'=>'id', 'instructions'=>'⚠️ Highly recommended: Select a featured itinerary to showcase on this charter page'],
      ['key'=>'ssyc_featured_custom_title', 'label'=>'Custom Title', 'name'=>'featured_custom_title', 'type'=>'text'],
      ['key'=>'ssyc_featured_summary', 'label'=>'Summary', 'name'=>'featured_summary', 'type'=>'textarea', 'rows'=>4, 'instructions'=>'80-120 words; can fallback to itinerary excerpt'],
      ['key'=>'ssyc_featured_cta_label', 'label'=>'CTA Label', 'name'=>'featured_cta_label', 'type'=>'text', 'default_value'=>'View Day-by-Day'],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 7: Charter Types
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_charter_types',
    'title' => 'Charter Types',
    'fields' => [
      ['key'=>'ssyc_charter_types', 'label'=>'Charter Types', 'name'=>'charter_types', 'type'=>'checkbox', 'choices'=>['bareboat'=>'Bareboat','skippered'=>'Skippered','catamaran'=>'Catamaran','crewed_luxury'=>'Crewed Luxury','gulet'=>'Gulet','by_cabin'=>'By Cabin']],
      [
        'key'=>'ssyc_charter_type_benefits', 'label'=>'Type Benefits', 'name'=>'charter_type_benefits', 'type'=>'repeater', 'layout'=>'block', 'button_label'=>'Add Type Benefits',
        'sub_fields'=>[
          ['key'=>'ssyc_type_key', 'label'=>'Type', 'name'=>'type_key', 'type'=>'select', 'choices'=>['bareboat'=>'Bareboat','skippered'=>'Skippered','catamaran'=>'Catamaran','crewed_luxury'=>'Crewed Luxury','gulet'=>'Gulet','by_cabin'=>'By Cabin']],
          [
            'key'=>'ssyc_benefit_points', 'label'=>'Benefit Points', 'name'=>'benefit_points', 'type'=>'repeater', 'min'=>2, 'max'=>5, 'layout'=>'table', 'button_label'=>'Add Benefit',
            'sub_fields'=>[
              ['key'=>'ssyc_benefit', 'label'=>'Benefit', 'name'=>'benefit', 'type'=>'text'],
            ]
          ],
        ]
      ],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 8: Interactive Map
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_map',
    'title' => 'Interactive Map',
    'fields' => [
      ['key'=>'ssyc_map_source', 'label'=>'Map Source', 'name'=>'map_source', 'type'=>'select', 'choices'=>['from_featured_itinerary'=>'From Featured Itinerary','manual_geojson'=>'Manual GeoJSON','none'=>'None'], 'default_value'=>'from_featured_itinerary', 'ui'=>1],
      ['key'=>'ssyc_map_geojson', 'label'=>'Map GeoJSON', 'name'=>'map_geojson', 'type'=>'textarea', 'rows'=>6, 'instructions'=>'FeatureCollection JSON', 'conditional_logic'=>[[['field'=>'ssyc_map_source','operator'=>'==','value'=>'manual_geojson']]]],
      ['key'=>'ssyc_map_height', 'label'=>'Map Height (px)', 'name'=>'map_height', 'type'=>'number', 'default_value'=>420, 'min'=>200, 'step'=>10],
      ['key'=>'ssyc_map_controls', 'label'=>'Map Controls', 'name'=>'map_controls', 'type'=>'checkbox', 'choices'=>['zoom'=>'Zoom','scale'=>'Scale','fullscreen'=>'Fullscreen'], 'default_value'=>['zoom','scale']],
      ['key'=>'ssyc_map_theme', 'label'=>'Map Theme', 'name'=>'map_theme', 'type'=>'select', 'choices'=>['light'=>'Light','dark'=>'Dark','satellite'=>'Satellite'], 'default_value'=>'light', 'ui'=>1],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 9: Weather
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_weather',
    'title' => 'Weather (Open-Meteo)',
    'fields' => [
      ['key'=>'ssyc_weather_enable', 'label'=>'Enable Weather', 'name'=>'weather_enable', 'type'=>'true_false', 'default_value'=>1],
      ['key'=>'ssyc_weather_lat', 'label'=>'Weather Latitude', 'name'=>'weather_lat', 'type'=>'number', 'step'=>'0.000001', 'instructions'=>'Defaults to Page Meta geo_lat'],
      ['key'=>'ssyc_weather_lon', 'label'=>'Weather Longitude', 'name'=>'weather_lon', 'type'=>'number', 'step'=>'0.000001', 'instructions'=>'Defaults to Page Meta geo_lon'],
      ['key'=>'ssyc_weather_range', 'label'=>'Weather Range', 'name'=>'weather_range', 'type'=>'select', 'choices'=>['current'=>'Current','next_7_days'=>'Next 7 Days','next_14_days'=>'Next 14 Days'], 'default_value'=>'current', 'ui'=>1],
      ['key'=>'ssyc_weather_cache_ttl_minutes', 'label'=>'Cache TTL (minutes)', 'name'=>'weather_cache_ttl_minutes', 'type'=>'number', 'default_value'=>180, 'min'=>30, 'step'=>30],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 10: Pricing Guide
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_pricing',
    'title' => 'Pricing Guide',
    'fields' => [
      [
        'key'=>'ssyc_pricing_table', 'label'=>'Pricing Table', 'name'=>'pricing_table', 'type'=>'repeater', 'layout'=>'table', 'button_label'=>'Add Season',
        'sub_fields'=>[
          ['key'=>'ssyc_season_label', 'label'=>'Season Label', 'name'=>'season_label', 'type'=>'text', 'instructions'=>'e.g., "Low (Apr-May)"'],
          ['key'=>'ssyc_bareboat_from', 'label'=>'Bareboat From', 'name'=>'bareboat_from', 'type'=>'number', 'min'=>0],
          ['key'=>'ssyc_catamaran_from', 'label'=>'Catamaran From', 'name'=>'catamaran_from', 'type'=>'number', 'min'=>0],
          ['key'=>'ssyc_crewed_from', 'label'=>'Crewed From', 'name'=>'crewed_from', 'type'=>'number', 'min'=>0],
        ]
      ],
      ['key'=>'ssyc_pricing_notes', 'label'=>'Pricing Notes', 'name'=>'pricing_notes', 'type'=>'wysiwyg', 'tabs'=>'all', 'toolbar'=>'basic', 'media_upload'=>0],
      ['key'=>'ssyc_currency_code', 'label'=>'Currency Code', 'name'=>'currency_code', 'type'=>'text', 'default_value'=>'EUR', 'maxlength'=>3],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 11: How It Works
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_process',
    'title' => 'How It Works (Process)',
    'fields' => [
      [
        'key'=>'ssyc_process_steps', 'label'=>'Process Steps', 'name'=>'process_steps', 'type'=>'repeater', 'min'=>3, 'max'=>5, 'layout'=>'row', 'button_label'=>'Add Step',
        'sub_fields'=>[
          ['key'=>'ssyc_step_title', 'label'=>'Step Title', 'name'=>'step_title', 'type'=>'text'],
          ['key'=>'ssyc_step_summary', 'label'=>'Step Summary', 'name'=>'step_summary', 'type'=>'textarea', 'rows'=>2],
          ['key'=>'ssyc_step_icon', 'label'=>'Step Icon', 'name'=>'step_icon', 'type'=>'text', 'instructions'=>'Icon name or image URL'],
        ]
      ],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 12: Why Book With Us
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_why_us',
    'title' => 'Why Book With Us',
    'fields' => [
      ['key'=>'ssyc_why_us_html', 'label'=>'Why Us Content', 'name'=>'why_us_html', 'type'=>'wysiwyg', 'tabs'=>'all', 'toolbar'=>'full', 'media_upload'=>1],
      [
        'key'=>'ssyc_trust_badges', 'label'=>'Trust Badges', 'name'=>'trust_badges', 'type'=>'repeater', 'layout'=>'table', 'button_label'=>'Add Badge',
        'sub_fields'=>[
          ['key'=>'ssyc_badge_image', 'label'=>'Badge Image', 'name'=>'badge_image', 'type'=>'image', 'return_format'=>'array'],
          ['key'=>'ssyc_badge_alt', 'label'=>'Alt Text', 'name'=>'badge_alt', 'type'=>'text'],
        ]
      ],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 13: Reviews
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_reviews',
    'title' => 'Reviews / Testimonials',
    'fields' => [
      ['key'=>'ssyc_reviews_mode', 'label'=>'Reviews Mode', 'name'=>'reviews_mode', 'type'=>'select', 'choices'=>['trustpilot_custom_v1'=>'Trustpilot Custom V1','none'=>'None'], 'default_value'=>'trustpilot_custom_v1', 'ui'=>1],
      ['key'=>'ssyc_tp_headline', 'label'=>'Headline', 'name'=>'tp_headline', 'type'=>'text', 'default_value'=>'Rated 4.9★ on Trustpilot', 'conditional_logic'=>[[['field'=>'ssyc_reviews_mode','operator'=>'==','value'=>'trustpilot_custom_v1']]]],
      ['key'=>'ssyc_tp_caption', 'label'=>'Caption', 'name'=>'tp_caption', 'type'=>'text', 'default_value'=>'200+ verified reviews', 'conditional_logic'=>[[['field'=>'ssyc_reviews_mode','operator'=>'==','value'=>'trustpilot_custom_v1']]]],
      ['key'=>'ssyc_tp_cta_label', 'label'=>'CTA Label', 'name'=>'tp_cta_label', 'type'=>'text', 'default_value'=>'Read Reviews', 'conditional_logic'=>[[['field'=>'ssyc_reviews_mode','operator'=>'==','value'=>'trustpilot_custom_v1']]]],
      ['key'=>'ssyc_tp_cta_url', 'label'=>'CTA URL', 'name'=>'tp_cta_url', 'type'=>'url', 'conditional_logic'=>[[['field'=>'ssyc_reviews_mode','operator'=>'==','value'=>'trustpilot_custom_v1']]]],
      ['key'=>'ssyc_tp_star_score', 'label'=>'Star Score', 'name'=>'tp_star_score', 'type'=>'number', 'min'=>0, 'max'=>5, 'step'=>'0.1', 'default_value'=>4.9, 'conditional_logic'=>[[['field'=>'ssyc_reviews_mode','operator'=>'==','value'=>'trustpilot_custom_v1']]]],
      ['key'=>'ssyc_tp_review_count', 'label'=>'Review Count', 'name'=>'tp_review_count', 'type'=>'text', 'default_value'=>'200+', 'conditional_logic'=>[[['field'=>'ssyc_reviews_mode','operator'=>'==','value'=>'trustpilot_custom_v1']]]],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 14: Lead Capture Form
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_form',
    'title' => 'Lead Capture Form',
    'fields' => [
    ['key'=>'ssyc_form_insert_position', 'label'=>'Form Position', 'name'=>'form_insert_position', 'type'=>'select', 'choices'=>['after_hero'=>'After Hero','mid_page'=>'Mid Page','sidebar_desktop'=>'Sidebar Desktop','footer'=>'Footer'], 'default_value'=>'sidebar_desktop', 'ui'=>1],
      ['key'=>'ssyc_form_shortcode', 'label'=>'Form Shortcode', 'name'=>'form_shortcode', 'type'=>'text', 'default_value'=>'[sailscanner_lead_form]'],
      // Removed: form_sticky_desktop
      ['key'=>'ssyc_form_mobile_behavior', 'label'=>'Mobile Behavior', 'name'=>'form_mobile_behavior', 'type'=>'select', 'choices'=>['inline'=>'Inline','cta_to_drawer'=>'CTA to Drawer'], 'default_value'=>'inline', 'ui'=>1],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 15: FAQs
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_faqs',
    'title' => 'FAQs',
    'fields' => [
      [
        'key'=>'ssyc_faqs', 'label'=>'FAQs', 'name'=>'faqs', 'type'=>'repeater', 'min'=>4, 'max'=>8, 'layout'=>'block', 'button_label'=>'Add FAQ',
        'sub_fields'=>[
          ['key'=>'ssyc_faq_question', 'label'=>'Question', 'name'=>'faq_question', 'type'=>'text'],
          ['key'=>'ssyc_faq_answer', 'label'=>'Answer', 'name'=>'faq_answer', 'type'=>'wysiwyg', 'tabs'=>'all', 'toolbar'=>'basic', 'media_upload'=>0],
        ]
      ],
      ['key'=>'ssyc_faqs_enable_schema', 'label'=>'Enable FAQ Schema', 'name'=>'faqs_enable_schema', 'type'=>'true_false', 'default_value'=>1],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 16: Related Content
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_related',
    'title' => 'Related Content',
    'fields' => [
      ['key'=>'ssyc_related_guides_by', 'label'=>'Related Guides By', 'name'=>'related_guides_by', 'type'=>'select', 'choices'=>['categories'=>'Categories','manual'=>'Manual'], 'default_value'=>'categories', 'ui'=>1],
      ['key'=>'ssyc_related_guides_categories', 'label'=>'Guides Categories', 'name'=>'related_guides_categories', 'type'=>'taxonomy', 'taxonomy'=>'category', 'field_type'=>'multi_select', 'return_format'=>'id', 'conditional_logic'=>[[['field'=>'ssyc_related_guides_by','operator'=>'==','value'=>'categories']]]],
      ['key'=>'ssyc_related_guides_limit', 'label'=>'Guides Limit', 'name'=>'related_guides_limit', 'type'=>'number', 'default_value'=>4, 'min'=>1, 'max'=>12, 'conditional_logic'=>[[['field'=>'ssyc_related_guides_by','operator'=>'==','value'=>'categories']]]],
      ['key'=>'ssyc_related_guides_manual', 'label'=>'Manual Guides', 'name'=>'related_guides_manual', 'type'=>'relationship', 'post_type'=>['destinations'], 'filters'=>['search','taxonomy'], 'max'=>6, 'return_format'=>'id', 'conditional_logic'=>[[['field'=>'ssyc_related_guides_by','operator'=>'==','value'=>'manual']]]],
      
      ['key'=>'ssyc_related_itineraries_by', 'label'=>'Related Itineraries By', 'name'=>'related_itineraries_by', 'type'=>'select', 'choices'=>['categories'=>'Categories','manual'=>'Manual'], 'default_value'=>'categories', 'ui'=>1],
      ['key'=>'ssyc_related_itineraries_categories', 'label'=>'Itineraries Categories', 'name'=>'related_itineraries_categories', 'type'=>'taxonomy', 'taxonomy'=>'product_cat', 'field_type'=>'multi_select', 'return_format'=>'id', 'conditional_logic'=>[[['field'=>'ssyc_related_itineraries_by','operator'=>'==','value'=>'categories']]]],
      ['key'=>'ssyc_related_itineraries_limit', 'label'=>'Itineraries Limit', 'name'=>'related_itineraries_limit', 'type'=>'number', 'default_value'=>3, 'min'=>1, 'max'=>12, 'conditional_logic'=>[[['field'=>'ssyc_related_itineraries_by','operator'=>'==','value'=>'categories']]]],
      ['key'=>'ssyc_related_itineraries_manual', 'label'=>'Manual Itineraries', 'name'=>'related_itineraries_manual', 'type'=>'relationship', 'post_type'=>['itinerary'], 'filters'=>['search','taxonomy'], 'max'=>6, 'return_format'=>'id', 'conditional_logic'=>[[['field'=>'ssyc_related_itineraries_by','operator'=>'==','value'=>'manual']]]],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 17: Footer CTA
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_footer_cta',
    'title' => 'Footer CTA',
    'fields' => [
      ['key'=>'ssyc_footer_cta_heading', 'label'=>'Heading', 'name'=>'footer_cta_heading', 'type'=>'text', 'instructions'=>'e.g., "Ready to Sail Mallorca?"'],
      ['key'=>'ssyc_footer_cta_subtext', 'label'=>'Subtext', 'name'=>'footer_cta_subtext', 'type'=>'textarea', 'rows'=>2],
      // Removed: footer_cta_button_label, footer_cta_button_target
      ['key'=>'ssyc_footer_cta_button_url', 'label'=>'Button URL', 'name'=>'footer_cta_button_url', 'type'=>'url'],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);

  /* ========================================
   * Group 18: Safety & Legal (V2)
   * ======================================== */
  acf_add_local_field_group([
    'key' => 'group_ssyc_safety_legal',
    'title' => 'Safety & Legal (V2)',
    'fields' => [
      ['key'=>'ssyc_safety_legal_html', 'label'=>'Safety & Legal Content', 'name'=>'safety_legal_html', 'type'=>'wysiwyg', 'tabs'=>'all', 'toolbar'=>'full', 'media_upload'=>1],
      [
        'key'=>'ssyc_download_links', 'label'=>'Download Links', 'name'=>'download_links', 'type'=>'repeater', 'layout'=>'table', 'button_label'=>'Add Document',
        'sub_fields'=>[
          ['key'=>'ssyc_doc_label', 'label'=>'Document Label', 'name'=>'doc_label', 'type'=>'text'],
          ['key'=>'ssyc_doc_file', 'label'=>'Document File', 'name'=>'doc_file', 'type'=>'file', 'return_format'=>'array'],
        ]
      ],
    ],
    'location' => [[['param'=>'post_type','operator'=>'==','value'=>'yacht_charter']]],
    'position' => 'normal',
  ]);
});


