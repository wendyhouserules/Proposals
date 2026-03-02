<?php
/**
 * REST: POST /sailscanner/v1/proposal (create proposal with ss_yacht_data, returns token + URL).
 * Reuses sailscanner_permission_check from sailscanner-rest-endpoints-extended (HMAC + capability).
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class SS_Proposal_REST {

	const MAX_YACHTS_PER_PROPOSAL = 25;

	public static function init() {
		add_action( 'rest_api_init', [ __CLASS__, 'register_routes' ] );
	}

	public static function register_routes() {
		if ( ! function_exists( 'sailscanner_permission_check' ) ) {
			if ( defined( 'SAILSCANNER_PROPOSALS_DEBUG' ) && SAILSCANNER_PROPOSALS_DEBUG ) {
				// phpcs:ignore WordPress.PHP.DevelopmentFunctions.error_log_error_log
				error_log( 'SS Proposals: sailscanner_permission_check not found; ensure sailscanner-rest-endpoints-extended is active.' );
			}
			return;
		}

		register_rest_route( 'sailscanner/v1', '/proposal', [
			'methods'             => 'POST',
			'callback'            => [ __CLASS__, 'create_proposal' ],
			'permission_callback' => 'sailscanner_permission_check',
			'args'                => [],
		] );
	}

	/**
	 * Create ss_proposal with ss_yacht_data; create ss_proposal_yacht posts and set ss_yacht_ids.
	 */
	public static function create_proposal( WP_REST_Request $req ) {
		$data = $req->get_json_params();
		if ( ! $data || empty( $data['ss_yacht_data'] ) || ! is_array( $data['ss_yacht_data'] ) ) {
			return new WP_Error( 'bad_request', 'ss_yacht_data required (array of yacht objects with display_name, images_json, etc.)', [ 'status' => 400 ] );
		}

		$yacht_data = $data['ss_yacht_data'];
		if ( count( $yacht_data ) > self::MAX_YACHTS_PER_PROPOSAL ) {
			return new WP_Error( 'bad_request', 'Max ' . self::MAX_YACHTS_PER_PROPOSAL . ' yachts per proposal', [ 'status' => 400 ] );
		}

		$token = self::generate_token();
		$now   = current_time( 'mysql' );

		$post_id = wp_insert_post( [
			'post_type'   => 'ss_proposal',
			'post_status' => 'publish',
			'post_title'  => 'Proposal ' . substr( $token, 0, 8 ) . '…',
			'post_date'   => $now,
		], true );
		if ( is_wp_error( $post_id ) ) {
			return $post_id;
		}

		update_post_meta( $post_id, 'ss_token', $token );
		update_post_meta( $post_id, 'ss_yacht_data', wp_json_encode( $yacht_data ) );
		update_post_meta( $post_id, 'ss_status', isset( $data['ss_status'] ) ? sanitize_text_field( $data['ss_status'] ) : 'sent' );
		update_post_meta( $post_id, 'ss_created_at', $now );
		if ( ! empty( $data['ss_expires_at'] ) ) {
			update_post_meta( $post_id, 'ss_expires_at', sanitize_text_field( $data['ss_expires_at'] ) );
		}
		if ( array_key_exists( 'ss_requirements_json', $data ) ) {
			$val = $data['ss_requirements_json'];
			update_post_meta( $post_id, 'ss_requirements_json', is_string( $val ) ? $val : wp_json_encode( $val ) );
		}
		$html_keys = [ 'ss_intro_html', 'ss_itinerary_html', 'ss_notes_html' ];
		foreach ( $html_keys as $key ) {
			if ( array_key_exists( $key, $data ) ) {
				update_post_meta( $post_id, $key, wp_kses_post( $data[ $key ] ) );
			}
		}
		if ( array_key_exists( 'ss_contact_whatsapp', $data ) ) {
			update_post_meta( $post_id, 'ss_contact_whatsapp', sanitize_text_field( $data['ss_contact_whatsapp'] ) );
		}
		if ( array_key_exists( 'ss_contact_email', $data ) ) {
			update_post_meta( $post_id, 'ss_contact_email', sanitize_email( $data['ss_contact_email'] ) );
		}
		if ( array_key_exists( 'ss_parse_warnings', $data ) ) {
			$val = $data['ss_parse_warnings'];
			update_post_meta( $post_id, 'ss_parse_warnings', is_string( $val ) ? $val : wp_json_encode( $val ) );
		}

		$yacht_ids = self::create_proposal_yacht_posts( $yacht_data );
		if ( ! empty( $yacht_ids ) ) {
			update_post_meta( $post_id, 'ss_yacht_ids', $yacht_ids );
		}

		$proposal_url = user_trailingslashit( home_url( '/proposals/' . $token . '/' ) );

		return [
			'post_id'      => $post_id,
			'token'        => $token,
			'proposal_url' => $proposal_url,
			'yacht_ids'    => $yacht_ids,
			'status'       => 'ok',
		];
	}

	/**
	 * Create one ss_proposal_yacht post per item; return array of post IDs.
	 *
	 * @param array $yacht_data Array of yacht objects (display_name, images_json, etc.)
	 * @return int[]
	 */
	private static function create_proposal_yacht_posts( array $yacht_data ) {
		$yacht_ids = [];
		foreach ( $yacht_data as $item ) {
			if ( ! is_array( $item ) ) {
				continue;
			}
			$title = isset( $item['display_name'] ) && (string) $item['display_name'] !== '' ? sanitize_text_field( (string) $item['display_name'] ) : __( 'Yacht', 'sailscanner-proposals' );
			$yacht_post_id = wp_insert_post( [
				'post_type'   => 'ss_proposal_yacht',
				'post_title'  => $title,
				'post_status' => 'publish',
				'post_author' => 1,
			], true );
			if ( is_wp_error( $yacht_post_id ) || $yacht_post_id <= 0 ) {
				continue;
			}
			foreach ( [ 'display_name', 'model', 'base_name', 'country', 'region' ] as $text_key ) {
				if ( isset( $item[ $text_key ] ) && (string) $item[ $text_key ] !== '' ) {
					update_post_meta( $yacht_post_id, $text_key, sanitize_text_field( (string) $item[ $text_key ] ) );
				}
			}
			foreach ( [ 'year', 'cabins', 'berths', 'wc' ] as $int_key ) {
				if ( isset( $item[ $int_key ] ) ) {
					update_post_meta( $yacht_post_id, $int_key, absint( $item[ $int_key ] ) );
				}
			}
			if ( isset( $item['length_m'] ) ) {
				update_post_meta( $yacht_post_id, 'length_m', floatval( $item['length_m'] ) );
			}
			foreach ( [ 'images_json', 'highlights_json', 'specs_json' ] as $json_key ) {
				if ( ! isset( $item[ $json_key ] ) ) {
					continue;
				}
				$val = $item[ $json_key ];
				$val = is_array( $val ) || is_object( $val ) ? wp_json_encode( $val ) : ( is_string( $val ) ? $val : wp_json_encode( [] ) );
				update_post_meta( $yacht_post_id, $json_key, $val );
			}
			$yacht_ids[] = $yacht_post_id;
		}
		return $yacht_ids;
	}

	private static function generate_token() {
		return bin2hex( random_bytes( 24 ) );
	}
}
