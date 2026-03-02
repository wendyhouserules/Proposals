<?php
/**
 * Template for Single Yacht Charter
 * 
 * Copy this file to your theme root to customize
 * Uses shortcodes for all content blocks
 */

get_header(); 

while ( have_posts() ) : the_post(); ?>

<article id="post-<?php the_ID(); ?>" <?php post_class('yacht-charter-single'); ?>>

  <div class="yacht-charter-container" style="max-width: 1200px; margin: 0 auto; padding: 2rem 1rem;">
    
    <div class="yacht-charter-grid" style="display: grid; grid-template-columns: 1fr; gap: 3rem;">
      
      <!-- Main Content Column -->
      <div class="yacht-charter-main">
        
        <?php 
        // Weather Chip
        echo do_shortcode('[ssyc_weather]');
        
        // Value Propositions
        echo do_shortcode('[ssyc_usps]');
        
        // SEO Intro
        echo do_shortcode('[ssyc_intro]');
        
        // Destination Highlights
        echo do_shortcode('[ssyc_highlights]');
        
        // Featured Itinerary
        echo do_shortcode('[ssyc_featured_itinerary]');
        
        // Interactive Map
        echo do_shortcode('[ssyc_map]');
        
        // Charter Types
        echo do_shortcode('[ssyc_charter_types]');
        
        // Pricing Guide
        echo do_shortcode('[ssyc_pricing]');
        
        // How It Works
        echo do_shortcode('[ssyc_process]');
        
        // Why Book With Us
        echo do_shortcode('[ssyc_why_us]');
        
        // Reviews / Trustpilot
        echo do_shortcode('[ssyc_reviews]');
        
        // Lead Form
        echo do_shortcode('[ssyc_lead_form]');
        
        // FAQs
        echo do_shortcode('[ssyc_faqs]');
        
        // Related Itineraries
        echo do_shortcode('[ssyc_related_itineraries]');
        
        // Related Guides
        echo do_shortcode('[ssyc_related_guides]');
        
        // Footer CTA
        echo do_shortcode('[ssyc_footer_cta]');
        ?>
        
      </div>
      
    </div>
    
  </div>
  
</article>

<?php 
endwhile;

get_footer();


