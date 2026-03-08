<?php
/**
 * Registers ss_proposal CPT. Publicly renderable but not discoverable; no archive; excluded from search/sitemap.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class SS_Proposal_CPT {

	public static function init() {
		add_action( 'init',           [ __CLASS__, 'register_cpt' ], 5 );
		add_action( 'add_meta_boxes', [ __CLASS__, 'add_meta_boxes' ] );
		add_action( 'save_post',      [ __CLASS__, 'save_requirements_meta_box' ], 10, 2 );
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
			'publicly_queryable'  => false, // Served via token route, not ?post_type=ss_proposal&p=123
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
			'labels'              => [
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
			'public'              => true,
			'publicly_queryable'  => true,
			'show_ui'             => true,
			'show_in_menu'        => true,
			'show_in_rest'        => true,
			'rewrite'             => [ 'slug' => 'proposal-yacht' ],
			'has_archive'         => false,
			'exclude_from_search' => true,
			'capability_type'     => 'post',
			'map_meta_cap'        => true,
			'supports'            => [ 'title' ],
			'menu_icon'           => 'dashicons-portfolio',
		] );
	}

	// ── Requirements meta box ──────────────────────────────────────────────────

	/**
	 * Register the "Your Requirements" meta box on the ss_proposal edit screen.
	 */
	public static function add_meta_boxes() {
		add_meta_box(
			'ss_proposal_requirements',
			__( 'Your Requirements (editable)', 'sailscanner-proposals' ),
			[ __CLASS__, 'render_requirements_meta_box' ],
			'ss_proposal',
			'normal',
			'high'
		);
	}

	/**
	 * Render the Requirements meta box.
	 *
	 * Pre-populates each field from the override (ss_answers_override) when set,
	 * otherwise falls back to the original ss_lead_json answers so the form always
	 * shows the current effective value.
	 *
	 * @param WP_Post $post
	 */
	public static function render_requirements_meta_box( $post ) {
		wp_nonce_field( 'ss_req_meta_nonce', 'ss_req_meta_nonce' );

		// Read original lead answers.
		$lead    = [];
		$lead_json = get_post_meta( $post->ID, 'ss_lead_json', true );
		if ( is_string( $lead_json ) ) {
			$dec = json_decode( $lead_json, true );
			if ( is_array( $dec ) ) {
				$lead = $dec;
			}
		}
		$orig = isset( $lead['answers'] ) && is_array( $lead['answers'] ) ? $lead['answers'] : [];

		// Read any existing overrides.
		$override = [];
		$override_json = get_post_meta( $post->ID, 'ss_answers_override', true );
		if ( is_string( $override_json ) && $override_json !== '' ) {
			$dec = json_decode( $override_json, true );
			if ( is_array( $dec ) ) {
				$override = $dec;
			}
		}

		// Helper: returns the effective value (override first, then original lead).
		$eff = function( $key ) use ( $orig, $override ) {
			if ( isset( $override[ $key ] ) && $override[ $key ] !== '' ) {
				return (string) $override[ $key ];
			}
			if ( isset( $orig[ $key ] ) ) {
				$v = $orig[ $key ];
				return is_array( $v ) ? implode( ', ', $v ) : (string) $v;
			}
			return '';
		};

		// Dates are nested: answers.dates.start / answers.dates.end.
		$dates_start = isset( $override['dates']['start'] ) && $override['dates']['start'] !== ''
			? $override['dates']['start']
			: ( $orig['dates']['start'] ?? '' );
		$dates_end   = isset( $override['dates']['end'] ) && $override['dates']['end'] !== ''
			? $override['dates']['end']
			: ( $orig['dates']['end'] ?? '' );

		$fields = [
			[ 'key' => '_dates_start',   'label' => 'Start date',   'value' => $dates_start,          'type' => 'date' ],
			[ 'key' => '_dates_end',     'label' => 'End date',     'value' => $dates_end,             'type' => 'date' ],
			[ 'key' => 'charterType',    'label' => 'Charter type', 'value' => $eff('charterType'),    'type' => 'text' ],
			[ 'key' => 'boatType',       'label' => 'Boat type',    'value' => $eff('boatType'),       'type' => 'text' ],
			[ 'key' => 'country',        'label' => 'Country',      'value' => $eff('country'),        'type' => 'text' ],
			[ 'key' => 'region',         'label' => 'Region',       'value' => $eff('region'),         'type' => 'text' ],
			[ 'key' => 'size',           'label' => 'Size (ft)',    'value' => $eff('size'),           'type' => 'text' ],
			[ 'key' => 'cabins',         'label' => 'Cabins',       'value' => $eff('cabins'),         'type' => 'text' ],
			[ 'key' => 'budget',         'label' => 'Budget',       'value' => $eff('budget'),         'type' => 'text' ],
			[ 'key' => 'experienceLevel','label' => 'Experience',   'value' => $eff('experienceLevel'),'type' => 'text' ],
		];
		?>
		<style>
			#ss_proposal_requirements .ss-req-grid {
				display: grid;
				grid-template-columns: 1fr 1fr;
				gap: 10px 24px;
				margin-top: 8px;
			}
			#ss_proposal_requirements .ss-req-field label {
				display: block;
				font-weight: 600;
				font-size: 11px;
				color: #666;
				margin-bottom: 3px;
				text-transform: uppercase;
				letter-spacing: .04em;
			}
			#ss_proposal_requirements .ss-req-field input {
				width: 100%;
				box-sizing: border-box;
			}
			#ss_proposal_requirements .ss-req-note {
				color: #888;
				font-size: 12px;
				margin: 10px 0 0;
				font-style: italic;
			}
		</style>
		<div class="ss-req-grid">
			<?php foreach ( $fields as $f ) : ?>
			<div class="ss-req-field">
				<label for="ss_req_<?php echo esc_attr( $f['key'] ); ?>"><?php echo esc_html( $f['label'] ); ?></label>
				<input
					type="<?php echo esc_attr( $f['type'] ); ?>"
					id="ss_req_<?php echo esc_attr( $f['key'] ); ?>"
					name="ss_req[<?php echo esc_attr( $f['key'] ); ?>]"
					value="<?php echo esc_attr( $f['value'] ); ?>"
					class="widefat"
				/>
			</div>
			<?php endforeach; ?>
		</div>
		<p class="ss-req-note">
			Values shown are the current effective values (your edits override the original lead data). Clear a field to revert it to the original. The original lead data is never modified.
		</p>
		<?php
	}

	/**
	 * Save the requirements meta box. Stores non-empty values in ss_answers_override.
	 * Deletes the meta entirely if everything is cleared (reverts to original lead data).
	 *
	 * @param int     $post_id
	 * @param WP_Post $post
	 */
	public static function save_requirements_meta_box( $post_id, $post ) {
		if (
			! isset( $_POST['ss_req_meta_nonce'] ) ||
			! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['ss_req_meta_nonce'] ) ), 'ss_req_meta_nonce' ) ||
			( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) ||
			! current_user_can( 'edit_post', $post_id ) ||
			$post->post_type !== 'ss_proposal'
		) {
			return;
		}

		$raw = isset( $_POST['ss_req'] ) && is_array( $_POST['ss_req'] ) ? $_POST['ss_req'] : [];

		$override  = [];
		$flat_keys = [ 'charterType', 'boatType', 'country', 'region', 'size', 'cabins', 'budget', 'experienceLevel' ];
		foreach ( $flat_keys as $k ) {
			$v = isset( $raw[ $k ] ) ? sanitize_text_field( wp_unslash( (string) $raw[ $k ] ) ) : '';
			if ( $v !== '' ) {
				$override[ $k ] = $v;
			}
		}

		// Dates stored nested: dates => [ start => ..., end => ... ].
		$dates_start = isset( $raw['_dates_start'] ) ? sanitize_text_field( wp_unslash( (string) $raw['_dates_start'] ) ) : '';
		$dates_end   = isset( $raw['_dates_end'] )   ? sanitize_text_field( wp_unslash( (string) $raw['_dates_end'] ) )   : '';
		if ( $dates_start !== '' || $dates_end !== '' ) {
			$override['dates'] = [];
			if ( $dates_start !== '' ) {
				$override['dates']['start'] = $dates_start;
			}
			if ( $dates_end !== '' ) {
				$override['dates']['end'] = $dates_end;
			}
		}

		if ( ! empty( $override ) ) {
			update_post_meta( $post_id, 'ss_answers_override', wp_json_encode( $override, JSON_UNESCAPED_UNICODE ) );
		} else {
			// All fields cleared — remove override so original lead data shows again.
			delete_post_meta( $post_id, 'ss_answers_override' );
		}
	}
}
