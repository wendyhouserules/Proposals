<?php
/**
 * Plugin Name: SailScanner Proposals
 * Description: Tokenized proposal pages for SailScanner (ss_proposal and ss_proposal_yacht CPTs, /proposals/{token}/, REST proposal endpoints). Optional: sailscanner-rest-endpoints-extended for HMAC on sailscanner/v1.
 * Version:     1.0.0
 * Author:      SailScanner
 * Requires at least: 6.0
 * Requires PHP: 7.4
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'SAILSCANNER_PROPOSALS_VERSION', '1.0.0' );
define( 'SAILSCANNER_PROPOSALS_PATH', plugin_dir_path( __FILE__ ) );
define( 'SAILSCANNER_PROPOSALS_URL', plugin_dir_url( __FILE__ ) );

// CPT: ss_proposal
require_once SAILSCANNER_PROPOSALS_PATH . 'includes/class-ss-proposal-cpt.php';
// Token routing and template loading
require_once SAILSCANNER_PROPOSALS_PATH . 'includes/class-ss-proposal-routing.php';
// REST: core wp/v2 (Basic auth only) + optional custom sailscanner/v1 (HMAC)
require_once SAILSCANNER_PROPOSALS_PATH . 'includes/class-ss-proposal-rest-core.php';
require_once SAILSCANNER_PROPOSALS_PATH . 'includes/class-ss-proposal-rest.php';
// Noindex, sitemap/search exclusion
require_once SAILSCANNER_PROPOSALS_PATH . 'includes/class-ss-proposal-seo.php';
// Template helpers (yacht display data, WhatsApp URL)
require_once SAILSCANNER_PROPOSALS_PATH . 'includes/class-ss-proposal-helpers.php';

SS_Proposal_CPT::init();
SS_Proposal_Routing::init();
SS_Proposal_REST_Core::init();
SS_Proposal_REST::init();
SS_Proposal_SEO::init();

// Prevent WordPress from auto-converting uploaded images to WebP.
// The server's WAF blocks .webp files from being served (406), so any WebP
// output — whether uploaded directly or converted by WordPress — breaks images.
// This keeps JPEG uploads as JPEG and PNG as PNG.
add_filter( 'wp_upload_image_mime_transforms', '__return_empty_array' );

register_activation_hook( __FILE__, function () {
	SS_Proposal_CPT::register_cpt();
	SS_Proposal_Routing::add_rewrite_rule();
	flush_rewrite_rules();
} );
