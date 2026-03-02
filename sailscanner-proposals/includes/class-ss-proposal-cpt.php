<?php
/**
 * Registers ss_proposal CPT. Publicly renderable but not discoverable; no archive; excluded from search/sitemap.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class SS_Proposal_CPT {

	public static function init() {
		add_action( 'init', [ __CLASS__, 'register_cpt' ], 5 );
	}

	public static function register_cpt() {
		$labels = [
			'name'               => _x( 'Proposals', 'post type general name', 'sailscanner-proposals' ),
			'singular_name'      => _x( 'Proposal', 'post type singular name', 'sailscanner-proposals' ),
			'menu_name'          => __( 'Proposals', 'sailscanner-proposals' ),
			'add_new'            => __( 'Add New', 'sailscanner-proposals' ),
			'add_new_item'       => __( 'Add New Proposal', 'sailscanner-proposals' ),
			'edit_item'          => __( 'Edit Proposal', 'sailscanner-proposals' ),
			'view_item'          => __( 'View Proposal', 'sailscanner-proposals' ),
			'all_items'          => __( 'All Proposals', 'sailscanner-proposals' ),
			'search_items'       => __( 'Search Proposals', 'sailscanner-proposals' ),
			'not_found'          => __( 'No proposals found.', 'sailscanner-proposals' ),
			'not_found_in_trash' => __( 'No proposals found in Trash.', 'sailscanner-proposals' ),
		];

		$args = [
			'labels'              => $labels,
			'public'              => true,
			'publicly_queryable'   => false, // We serve via token route, not ?post_type=ss_proposal&p=123
			'show_ui'             => true,
			'show_in_menu'        => true,
			'show_in_rest'        => true,
			'rewrite'             => false,
			'has_archive'         => false,
			'exclude_from_search' => true,
			'capability_type'     => 'post',
			'map_meta_cap'        => true,
		'supports'            => [ 'title', 'editor' ],
		'menu_icon'           => 'dashicons-media-document',
		];

		register_post_type( 'ss_proposal', $args );

		// Proposal yacht picks: one post per yacht so "View details" has a real URL. Not for guide content.
		register_post_type( 'ss_proposal_yacht', [
			'labels'                => [
				'name'               => _x( 'Proposal Yachts', 'post type general name', 'sailscanner-proposals' ),
				'singular_name'      => _x( 'Proposal Yacht', 'post type singular name', 'sailscanner-proposals' ),
				'menu_name'          => __( 'Proposal Yachts', 'sailscanner-proposals' ),
				'add_new'            => __( 'Add New', 'sailscanner-proposals' ),
				'add_new_item'       => __( 'Add New Proposal Yacht', 'sailscanner-proposals' ),
				'edit_item'          => __( 'Edit Proposal Yacht', 'sailscanner-proposals' ),
				'view_item'          => __( 'View Proposal Yacht', 'sailscanner-proposals' ),
				'all_items'          => __( 'All Proposal Yachts', 'sailscanner-proposals' ),
				'not_found'          => __( 'No proposal yachts found.', 'sailscanner-proposals' ),
			],
			'public'                => true,
			'publicly_queryable'    => true,
			'show_ui'               => true,
			'show_in_menu'          => true,
			'show_in_rest'          => true,
			'rewrite'               => [ 'slug' => 'proposal-yacht' ],
			'has_archive'           => false,
			'exclude_from_search'   => true,
			'capability_type'      => 'post',
			'map_meta_cap'         => true,
			'supports'              => [ 'title' ],
			'menu_icon'             => 'dashicons-portfolio',
		] );
	}
}
