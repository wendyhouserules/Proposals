<?php
/**
 * Core REST (wp/v2): expose ss_proposal and ss_proposal_yacht with meta so scripts can use Basic auth only.
 * No HMAC required. Token generated server-side on proposal create.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class SS_Proposal_REST_Core {

	public static function init() {
		add_action( 'rest_api_init', [ __CLASS__, 'register_rest_fields' ] );
		add_filter( 'rest_pre_insert_ss_proposal', [ __CLASS__, 'default_proposal_title' ], 10, 2 );
		add_action( 'rest_after_insert_ss_proposal', [ __CLASS__, 'after_insert_proposal' ], 10, 3 );
	}

	/** Set default title so REST create succeeds; after_insert will replace with token-based title. */
	public static function default_proposal_title( $prepared_post, $request ) {
		// WordPress passes stdClass (object), not array.
		$title = is_object( $prepared_post ) ? ( $prepared_post->post_title ?? '' ) : ( $prepared_post['post_title'] ?? '' );
		if ( $title !== '' ) {
			return $prepared_post;
		}
		if ( is_object( $prepared_post ) ) {
			$prepared_post->post_title = 'Proposal (draft)';
		} else {
			$prepared_post['post_title'] = 'Proposal (draft)';
		}
		return $prepared_post;
	}

	public static function register_rest_fields() {
		// --- ss_proposal ---
		$proposal_meta = [
			'ss_token'                 => [ 'type' => 'string', 'description' => 'Server-generated if omitted' ],
			'ss_yacht_ids'              => [ 'type' => 'array', 'items' => [ 'type' => 'integer' ], 'description' => 'ss_proposal_yacht post IDs (set server-side from ss_yacht_data on create)' ],
			'ss_yacht_data'             => [ 'type' => 'array', 'items' => [ 'type' => 'object' ], 'description' => 'Yacht picks: array of objects with display_name, images_json, highlights_json, cabins, berths, etc. Server creates ss_proposal_yacht posts on proposal create.' ],
			'ss_intro_html'             => [ 'type' => 'string' ],
			'ss_itinerary_html'         => [ 'type' => 'string' ],
			'ss_notes_html'             => [ 'type' => 'string' ],
			'ss_contact_whatsapp'       => [ 'type' => 'string' ],
			'ss_contact_email'          => [ 'type' => 'string' ],
			'ss_requirements_json'      => [ 'type' => [ 'string', 'object' ] ],
			'ss_lead_json'              => [ 'type' => [ 'string', 'object' ], 'description' => 'Lead payload (answers, contact) for intro and requirements display' ],
			'ss_itinerary_link_url'      => [ 'type' => 'string' ],
			'ss_itinerary_link_title'    => [ 'type' => 'string' ],
			'ss_itinerary_link_summary'  => [ 'type' => 'string' ],
			'ss_itinerary_link_image'    => [ 'type' => 'string' ],
			'ss_itinerary_link_days'     => [ 'type' => 'string' ],
			'ss_itinerary_link_distance' => [ 'type' => 'string' ],
			'ss_itinerary_link_region'   => [ 'type' => 'string' ],
			'ss_group_by_base'           => [ 'type' => 'boolean', 'description' => 'When true, yacht cards are grouped by charter base in the proposal.' ],
			'ss_status'                 => [ 'type' => 'string' ],
			'ss_created_at'             => [ 'type' => 'string' ],
			'ss_expires_at'             => [ 'type' => 'string' ],
		];
		foreach ( $proposal_meta as $key => $schema ) {
			$is_token = ( $key === 'ss_token' );
			register_rest_field( 'ss_proposal', $key, [
				'get_callback'   => function ( $post ) use ( $key ) {
					$post_id = self::rest_post_id( $post );
					if ( ! $post_id ) {
						return $key === 'ss_requirements_json' ? [] : '';
					}
					$val = get_post_meta( $post_id, $key, true );
					if ( $key === 'ss_requirements_json' && is_string( $val ) ) {
						$decoded = json_decode( $val, true );
						return $decoded !== null ? $decoded : $val;
					}
					if ( $key === 'ss_lead_json' && is_string( $val ) ) {
						$decoded = json_decode( $val, true );
						return $decoded !== null ? $decoded : $val;
					}
					if ( $key === 'ss_yacht_data' && is_string( $val ) ) {
						$decoded = json_decode( $val, true );
						return is_array( $decoded ) ? $decoded : [];
					}
					return $val;
				},
				'update_callback' => function ( $value, $post ) use ( $key, $is_token ) {
					$post_id = self::rest_post_id( $post );
					if ( ! $post_id ) {
						return new \WP_Error( 'invalid_post', 'Post ID not available', [ 'status' => 500 ] );
					}
					if ( $is_token ) {
						$token = is_string( $value ) && $value !== '' ? $value : self::generate_token();
						update_post_meta( $post_id, 'ss_token', $token );
						return true;
					}
					if ( $key === 'ss_yacht_ids' ) {
						$ids = is_array( $value ) ? array_map( 'absint', $value ) : [];
						update_post_meta( $post_id, $key, $ids );
						return true;
					}
				if ( $key === 'ss_yacht_data' ) {
					$data = is_array( $value ) ? $value : [];
					update_post_meta( $post_id, $key, wp_json_encode( $data, JSON_UNESCAPED_UNICODE ) );
					return true;
				}
				if ( $key === 'ss_requirements_json' ) {
					$val = is_string( $value ) ? $value : wp_json_encode( is_array( $value ) ? $value : [], JSON_UNESCAPED_UNICODE );
					update_post_meta( $post_id, $key, $val );
					return true;
				}
					if ( in_array( $key, [ 'ss_intro_html', 'ss_itinerary_html', 'ss_notes_html' ], true ) ) {
						update_post_meta( $post_id, $key, wp_kses_post( is_string( $value ) ? $value : '' ) );
						return true;
					}
					if ( $key === 'ss_contact_email' ) {
						update_post_meta( $post_id, $key, sanitize_email( is_string( $value ) ? $value : '' ) );
						return true;
					}
				if ( $key === 'ss_lead_json' ) {
					$val = is_string( $value ) ? $value : wp_json_encode( is_array( $value ) ? $value : [], JSON_UNESCAPED_UNICODE );
					update_post_meta( $post_id, $key, $val );
					return true;
				}
				if ( $key === 'ss_group_by_base' ) {
					update_post_meta( $post_id, $key, (bool) $value ? '1' : '0' );
					return true;
				}
			if ( in_array( $key, [ 'ss_itinerary_link_url', 'ss_itinerary_link_image' ], true ) ) {
				$sanitized = esc_url_raw( is_string( $value ) ? $value : '' );
				$old_url   = get_post_meta( $post_id, $key, true );
				update_post_meta( $post_id, $key, $sanitized );
				// When the itinerary URL is set (or changed) via REST, auto-fetch metadata
				// (title, image, summary, days, distance, region) from the same-site WP post
				// so the proposal template can render the full itinerary card.
				if ( $key === 'ss_itinerary_link_url' && $sanitized && $sanitized !== $old_url ) {
					SS_Proposal_CPT::fetch_and_save_itinerary_meta( $post_id, $sanitized );
				}
				return true;
			}
					if ( in_array( $key, [ 'ss_itinerary_link_title', 'ss_itinerary_link_summary' ], true ) ) {
						update_post_meta( $post_id, $key, sanitize_text_field( is_string( $value ) ? $value : '' ) );
						return true;
					}
					update_post_meta( $post_id, $key, sanitize_text_field( is_string( $value ) ? $value : (string) $value ) );
					return true;
				},
				'schema' => array_merge( [ 'description' => $key ], $schema ),
			] );
		}

		// --- ss_proposal_yacht (proposal picks: display meta for "View details" pages) ---
		$proposal_yacht_meta = [
			'display_name'    => [ 'type' => 'string' ],
			'model'           => [ 'type' => 'string' ],
			'year'            => [ 'type' => 'integer' ],
			'length_m'        => [ 'type' => 'number' ],
			'cabins'          => [ 'type' => 'integer' ],
			'berths'          => [ 'type' => 'integer' ],
			'wc'              => [ 'type' => 'integer' ],
			'base_name'       => [ 'type' => 'string' ],
			'country'         => [ 'type' => 'string' ],
			'region'          => [ 'type' => 'string' ],
			'images_json'     => [ 'type' => [ 'array', 'string' ] ],
			'highlights_json' => [ 'type' => [ 'array', 'string' ] ],
			'specs_json'      => [ 'type' => [ 'array', 'string', 'object' ] ],
			'prices_json'     => [ 'type' => [ 'array', 'string', 'object' ] ],
			'charter_json'       => [ 'type' => [ 'array', 'string', 'object' ] ],
			'layout_image_url'   => [ 'type' => 'string' ],
		];
		foreach ( $proposal_yacht_meta as $key => $schema ) {
			register_rest_field( 'ss_proposal_yacht', $key, [
				'get_callback'    => function ( $post ) use ( $key ) {
					$post_id = self::rest_post_id( $post );
					if ( ! $post_id ) {
						return in_array( $key, [ 'images_json', 'highlights_json', 'specs_json', 'prices_json', 'charter_json' ], true ) ? [] : '';
					}
					$val = get_post_meta( $post_id, $key, true );
					if ( in_array( $key, [ 'images_json', 'highlights_json', 'specs_json', 'prices_json', 'charter_json' ], true ) && is_string( $val ) ) {
						$decoded = json_decode( $val, true );
						return $decoded !== null ? $decoded : $val;
					}
					return $val;
				},
				'update_callback'  => function ( $value, $post ) use ( $key ) {
			if ( in_array( $key, [ 'images_json', 'highlights_json', 'specs_json', 'prices_json', 'charter_json' ], true ) ) {
					$val = is_array( $value ) || is_object( $value ) ? wp_json_encode( $value, JSON_UNESCAPED_UNICODE ) : ( is_string( $value ) ? $value : wp_json_encode( [], JSON_UNESCAPED_UNICODE ) );
					update_post_meta( $post->ID, $key, $val );
					return true;
				}
					if ( in_array( $key, [ 'year', 'cabins', 'berths', 'wc' ], true ) ) {
						update_post_meta( $post->ID, $key, absint( $value ) );
						return true;
					}
				if ( $key === 'length_m' ) {
					update_post_meta( $post->ID, $key, floatval( $value ) );
					return true;
				}
				if ( $key === 'layout_image_url' ) {
					update_post_meta( $post->ID, $key, esc_url_raw( is_string( $value ) ? $value : '' ) );
					return true;
				}
				update_post_meta( $post->ID, $key, sanitize_text_field( is_string( $value ) ? $value : (string) $value ) );
				return true;
			},
			'schema' => array_merge( [ 'description' => $key ], $schema ),
			] );
		}

		// Read-only proposal URL
		register_rest_field( 'ss_proposal', 'proposal_url', [
			'get_callback' => function ( $post ) {
				$post_id = self::rest_post_id( $post );
				if ( ! $post_id ) {
					return '';
				}
				$token = get_post_meta( $post_id, 'ss_token', true );
				if ( ! is_string( $token ) || $token === '' ) {
					return '';
				}
				return user_trailingslashit( home_url( '/proposals/' . $token . '/' ) );
			},
			'schema'       => [ 'type' => 'string', 'readonly' => true, 'description' => 'Public proposal URL' ],
		] );
	}

	/**
	 * Get post ID from REST callback param (WordPress may pass array or WP_Post).
	 * Prevents 500 when get_callback receives object and code uses $post['id'].
	 */
	public static function rest_post_id( $post ) {
		if ( is_array( $post ) && isset( $post['id'] ) ) {
			return (int) $post['id'];
		}
		if ( is_object( $post ) && isset( $post->ID ) ) {
			return (int) $post->ID;
		}
		return 0;
	}

	public static function return_empty() {
		return '';
	}

	public static function after_insert_proposal( $post, $request, $creating ) {
		if ( ! $creating ) {
			return;
		}
		$post_id = is_object( $post ) && isset( $post->ID ) ? (int) $post->ID : 0;
		if ( $post_id <= 0 ) {
			return;
		}
		// Large proposals (many yachts) can exceed the default PHP time limit.
		// set_time_limit() resets the countdown; 0 = no limit for this request only.
		set_time_limit( 0 );
		$token = get_post_meta( $post_id, 'ss_token', true );
		if ( ! is_string( $token ) || $token === '' ) {
			$token = self::generate_token();
			update_post_meta( $post_id, 'ss_token', $token );
		}
		// Build the title update args; also seed post_content on first creation so it's editable.
		$update_args = [
			'ID'         => $post_id,
			'post_title' => 'Proposal ' . substr( $token, 0, 8 ) . '...',
		];
		if ( get_post_field( 'post_content', $post_id ) === '' ) {
			// Prefer AI-generated intro from the request body directly —
			// post_meta hasn't been written yet when this hook fires (REST fields
			// are saved by update_additional_fields_for_object which runs after
			// rest_after_insert on some WP versions), so we read from $request.
			$ss_intro = '';
			if ( $request instanceof \WP_REST_Request ) {
				$raw = $request->get_param( 'ss_intro_html' );
				if ( is_string( $raw ) ) {
					$ss_intro = trim( $raw );
				}
			}
			// Fallback: try post_meta in case the meta was already saved.
			if ( $ss_intro === '' ) {
				$meta_val = get_post_meta( $post_id, 'ss_intro_html', true );
				if ( is_string( $meta_val ) ) {
					$ss_intro = trim( $meta_val );
				}
			}
			if ( $ss_intro !== '' ) {
				$update_args['post_content'] = wp_kses_post( $ss_intro );
			} else {
				$lead_raw = $request instanceof \WP_REST_Request ? $request->get_param( 'ss_lead_json' ) : null;
				$lead_arr = [];
				if ( is_array( $lead_raw ) ) {
					$lead_arr = $lead_raw;
				} elseif ( is_string( $lead_raw ) ) {
					$decoded  = json_decode( $lead_raw, true );
					$lead_arr = is_array( $decoded ) ? $decoded : [];
				} else {
					$lead_raw_meta = get_post_meta( $post_id, 'ss_lead_json', true );
					if ( is_string( $lead_raw_meta ) ) {
						$decoded  = json_decode( $lead_raw_meta, true );
						$lead_arr = is_array( $decoded ) ? $decoded : [];
					}
				}
				$intro = self::generate_intro_content( $lead_arr );
				if ( $intro !== '' ) {
					$update_args['post_content'] = $intro;
				}
			}
		}
		wp_update_post( $update_args );
		if ( get_post_meta( $post_id, 'ss_created_at', true ) === '' ) {
			update_post_meta( $post_id, 'ss_created_at', current_time( 'mysql' ) );
		}
		if ( get_post_meta( $post_id, 'ss_status', true ) === '' ) {
			update_post_meta( $post_id, 'ss_status', 'sent' );
		}

		// Create ss_proposal_yacht posts from ss_yacht_data so "View details" has a real URL.
		$yacht_data = get_post_meta( $post_id, 'ss_yacht_data', true );
		if ( is_string( $yacht_data ) ) {
			$yacht_data = json_decode( $yacht_data, true );
		}
		// Fallback: read directly from the REST request if post meta is empty.
		// This handles cases where update_post_meta failed silently (e.g. wp_json_encode
		// returned false for a large payload, or a WAF stripped the meta write).
		if ( ( ! is_array( $yacht_data ) || empty( $yacht_data ) ) && $request instanceof WP_REST_Request ) {
			$req_val = $request->get_param( 'ss_yacht_data' );
			if ( is_array( $req_val ) && ! empty( $req_val ) ) {
				$yacht_data = $req_val;
				update_post_meta( $post_id, 'ss_yacht_data', wp_json_encode( $yacht_data, JSON_UNESCAPED_UNICODE ) );
			}
		}
		if ( ! is_array( $yacht_data ) || empty( $yacht_data ) ) {
			return;
		}
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
			if ( isset( $item['layout_image_url'] ) && (string) $item['layout_image_url'] !== '' ) {
				update_post_meta( $yacht_post_id, 'layout_image_url', esc_url_raw( (string) $item['layout_image_url'] ) );
			}
			foreach ( [ 'year', 'cabins', 'berths', 'wc' ] as $int_key ) {
				if ( isset( $item[ $int_key ] ) ) {
					update_post_meta( $yacht_post_id, $int_key, absint( $item[ $int_key ] ) );
				}
			}
			if ( isset( $item['length_m'] ) ) {
				update_post_meta( $yacht_post_id, 'length_m', floatval( $item['length_m'] ) );
			}
			foreach ( [ 'images_json', 'highlights_json', 'specs_json', 'prices_json', 'charter_json' ] as $json_key ) {
				if ( ! isset( $item[ $json_key ] ) ) {
					continue;
				}
				$val = $item[ $json_key ];
				$val = is_array( $val ) || is_object( $val ) ? wp_json_encode( $val, JSON_UNESCAPED_UNICODE ) : ( is_string( $val ) ? $val : wp_json_encode( [], JSON_UNESCAPED_UNICODE ) );
				update_post_meta( $yacht_post_id, $json_key, $val );
			}
			$yacht_ids[] = $yacht_post_id;
		}
		if ( ! empty( $yacht_ids ) ) {
			update_post_meta( $post_id, 'ss_yacht_ids', $yacht_ids );
		}
	}

	/**
	 * Build a plain-text-style intro HTML for post_content (no CTA buttons — those come from the template).
	 * Saved on first proposal creation so the admin can edit it in the block editor.
	 *
	 * @param array $lead Lead payload (answers, contact).
	 * @return string HTML paragraphs, or empty string if no lead data.
	 */
	private static function generate_intro_content( array $lead ): string {
		$answers = isset( $lead['answers'] ) && is_array( $lead['answers'] ) ? $lead['answers'] : [];
		// Support both lead.contact and lead.answers.contact layouts.
		$contact = [];
		if ( isset( $lead['contact'] ) && is_array( $lead['contact'] ) && ! empty( $lead['contact'] ) ) {
			$contact = $lead['contact'];
		} elseif ( isset( $answers['contact'] ) && is_array( $answers['contact'] ) ) {
			$contact = $answers['contact'];
		}
		$name = isset( $contact['name'] ) ? esc_html( trim( (string) $contact['name'] ) ) : '';

		$charter_type = isset( $answers['charterType'] ) ? esc_html( ucfirst( trim( (string) $answers['charterType'] ) ) ) : 'charter';
		$boat_type    = isset( $answers['boatType'] )    ? esc_html( ucfirst( trim( (string) $answers['boatType'] ) ) )    : 'yacht';
		$country      = isset( $answers['country'] )     ? esc_html( trim( (string) $answers['country'] ) )                : 'your chosen area';
		$dates_str    = isset( $answers['dates']['start'] ) ? esc_html( trim( (string) $answers['dates']['start'] ) )      : 'the specified dates';

		$greeting = $name ? "Hi {$name}," : 'Hi,';

		return implode( "\n\n", [
			"<p>{$greeting}</p>",
			"<p>As requested, here is an example sailing itinerary and some yacht options for your {$charter_type} {$boat_type} charter in {$country} on {$dates_str}.</p>",
			'<p>Please let me know your thoughts and if you need any more information.</p>',
			'<p>You can contact me via email or WhatsApp using the links below.</p>',
			'<p>Chris</p>',
		] );
	}

	private static function generate_token() {
		return bin2hex( random_bytes( 24 ) );
	}
}
