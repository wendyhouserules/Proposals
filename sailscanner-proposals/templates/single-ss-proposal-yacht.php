<?php
/**
 * Single ss_proposal_yacht template: premium detail page for a proposal yacht pick.
 * Noindex set by SS_Proposal_SEO. Never display provider/operator name or source URLs.
 *
 * @package SailScanner_Proposals
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$yacht_id = get_the_ID();
$yacht    = SS_Proposal_Helpers::get_yacht_display_data( $yacht_id );
if ( empty( $yacht ) ) {
	$yacht = [
		'id'               => 0,
		'display_name'     => get_the_title(),
		'url'              => get_permalink(),
		'image_url'        => '',
		'images'           => [],
		'layout_image_url' => '',
		'highlights'       => [],
		'specs'            => [],
		'prices'           => [],
		'charter'          => [],
		'cabins'           => 0,
		'berths'           => 0,
		'length_m'         => '',
		'year'             => 0,
		'base_name'        => '',
		'country'          => '',
		'region'           => '',
		'model'            => '',
	];
}

wp_enqueue_style( 'ss-proposals-portal', SAILSCANNER_PROPOSALS_URL . 'assets/proposal-portal.css', [], SAILSCANNER_PROPOSALS_VERSION );
wp_enqueue_style(
	'ss-proposals-material-symbols',
	'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0',
	[],
	null
);

// --- Prepare data ---
$charter         = is_array( $yacht['charter'] ?? null ) ? $yacht['charter'] : [];
$charter_html    = SS_Proposal_Helpers::render_charter_slots( $charter );
$gallery_images  = array_values( array_filter( (array) $yacht['images'], [ 'SS_Proposal_Helpers', 'is_real_yacht_image' ] ) );
if ( empty( $gallery_images ) && SS_Proposal_Helpers::is_real_yacht_image( $yacht['image_url'] ?? '' ) ) {
	$gallery_images = [ $yacht['image_url'] ];
}
$layout_image    = $yacht['layout_image_url'] ?? '';
$gallery_id      = 'ssg-yacht-' . absint( $yacht_id );

$contact_wa    = get_option( 'ss_proposals_contact_whatsapp', '' );
$contact_email = get_option( 'ss_proposals_contact_email', '' );
$wa_message    = sprintf( __( "Hi, I'd like more information about %s", 'sailscanner-proposals' ), $yacht['display_name'] );
$wa_url        = $contact_wa ? SS_Proposal_Helpers::whatsapp_url( $contact_wa, $wa_message ) : '';

// Charter price for sidebar summary
$charter_price = ! empty( $yacht['prices']['charter_price'] ) ? $yacht['prices']['charter_price'] : '';
$base_price    = ! empty( $yacht['prices']['base_price'] ) ? $yacht['prices']['base_price'] : '';

// Build sidebar date line — for multi-slot yachts use the first slot's dates.
$sidebar_dates = '';
$_charter_first = ( ! empty( $charter['slots'] ) && is_array( $charter['slots'] ) ) ? $charter['slots'][0] : $charter;
$_date_parts    = [];
if ( ! empty( $_charter_first['date_from'] ) ) {
	$_from_bits    = array_filter( [ $_charter_first['date_from'], $_charter_first['checkin'] ?? '' ] );
	$_date_parts[] = implode( ', ', $_from_bits );
}
if ( ! empty( $_charter_first['date_to'] ) ) {
	$_to_bits      = array_filter( [ $_charter_first['date_to'], $_charter_first['checkout'] ?? '' ] );
	$_date_parts[] = implode( ', ', $_to_bits );
}
if ( ! empty( $_date_parts ) ) {
	$sidebar_dates = implode( ' → ', $_date_parts );
}

// Key stat pills: pull from specs when available, fall back to direct fields
$stat_map = [];
foreach ( $yacht['specs'] as $spec ) {
	$stat_map[ strtolower( $spec['label'] ) ] = $spec['value'];
}
$stat_year   = $yacht['year']     ?: ( $stat_map['year']   ?? '' );
$stat_length = $stat_map['length'] ?? ( $yacht['length_m'] ? $yacht['length_m'] . 'm' : '' );
$stat_cabins = $stat_map['cabins'] ?? ( $yacht['cabins'] ? $yacht['cabins'] : '' );
$stat_berths = $stat_map['berths'] ?? ( $yacht['berths'] ? $yacht['berths'] : '' );

$has_prices  = ! empty( $yacht['prices'] ) && is_array( $yacht['prices'] );
$has_charter = $charter_html !== '';
$has_specs   = ! empty( $yacht['specs'] );
$has_equip   = ! empty( $yacht['highlights'] );

get_header();
?>

<div class="ss-yacht-page">
	<div class="ss-yacht-page-inner">

		<!-- Page header: title + key stats -->
		<header class="ss-yacht-page-header">
			<h1 class="ss-yacht-page-title"><?php echo esc_html( $yacht['display_name'] ); ?></h1>
			<?php if ( $stat_year || $stat_length || $stat_cabins || $stat_berths ) : ?>
			<div class="ss-yacht-stats-bar">
				<?php if ( $stat_year ) : ?>
					<span class="ss-yacht-stat-pill">
						<span class="material-symbols-outlined" aria-hidden="true">calendar_today</span>
						<?php echo esc_html( $stat_year ); ?>
					</span>
				<?php endif; ?>
				<?php if ( $stat_length ) : ?>
					<span class="ss-yacht-stat-pill">
						<span class="material-symbols-outlined" aria-hidden="true">straighten</span>
						<?php echo esc_html( $stat_length ); ?>
					</span>
				<?php endif; ?>
				<?php if ( $stat_cabins ) : ?>
					<span class="ss-yacht-stat-pill">
						<span class="material-symbols-outlined" aria-hidden="true">bed</span>
						<?php echo esc_html( $stat_cabins ); ?> <?php esc_html_e( 'cabins', 'sailscanner-proposals' ); ?>
					</span>
				<?php endif; ?>
				<?php if ( $stat_berths ) : ?>
					<span class="ss-yacht-stat-pill">
						<span class="material-symbols-outlined" aria-hidden="true">people</span>
						<?php echo esc_html( $stat_berths ); ?> <?php esc_html_e( 'berths', 'sailscanner-proposals' ); ?>
					</span>
				<?php endif; ?>
			</div>
			<?php endif; ?>
		</header>

		<!-- Two-column layout: main content + sticky sidebar -->
		<div class="ss-yacht-layout">

			<!-- LEFT: gallery + all detail sections -->
			<div class="ss-yacht-main">

				<!-- Gallery -->
				<?php if ( ! empty( $gallery_images ) ) : ?>
				<div class="ss-proposal-yacht-gallery" id="<?php echo esc_attr( $gallery_id ); ?>">
					<div class="ss-proposal-yacht-gallery-main">
						<img class="ss-proposal-gallery-main-img"
							src="<?php echo esc_url( $gallery_images[0] ); ?>"
							alt="<?php echo esc_attr( $yacht['display_name'] ); ?>"
							loading="eager" />
					</div>
					<?php if ( count( $gallery_images ) > 1 ) : ?>
					<div class="ss-proposal-yacht-gallery-thumbs" role="list" aria-label="<?php esc_attr_e( 'Yacht photos', 'sailscanner-proposals' ); ?>">
						<?php foreach ( $gallery_images as $ti => $thumb_url ) : ?>
						<button class="ss-proposal-yacht-gallery-thumb<?php echo $ti === 0 ? ' is-active' : ''; ?>"
							type="button"
							data-gallery="<?php echo esc_attr( $gallery_id ); ?>"
							data-src="<?php echo esc_url( $thumb_url ); ?>"
							aria-label="<?php echo esc_attr( sprintf( __( 'View photo %d', 'sailscanner-proposals' ), $ti + 1 ) ); ?>"
							role="listitem">
							<img src="<?php echo esc_url( $thumb_url ); ?>" alt="" loading="lazy" />
						</button>
						<?php endforeach; ?>
					</div>
					<?php endif; ?>
				</div>
				<?php else : ?>
				<div class="ss-yacht-gallery-placeholder ss-proposal-card">
					<span class="material-symbols-outlined" aria-hidden="true">sailing</span>
				</div>
				<?php endif; ?>

			<!-- Charter Details -->
			<?php if ( $has_charter ) : ?>
			<section class="ss-yacht-detail-section" id="charter-details">
				<h2 class="ss-yacht-section-title">
					<span class="material-symbols-outlined" aria-hidden="true">anchor</span>
					<?php esc_html_e( 'Charter Details', 'sailscanner-proposals' ); ?>
				</h2>
				<?php echo $charter_html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
			</section>
			<?php endif; ?>

				<!-- Specification -->
				<?php if ( $has_specs || $yacht['cabins'] || $yacht['year'] ) : ?>
				<section class="ss-yacht-detail-section" id="specification">
					<h2 class="ss-yacht-section-title">
						<span class="material-symbols-outlined" aria-hidden="true">info</span>
						<?php esc_html_e( 'Specification', 'sailscanner-proposals' ); ?>
					</h2>
					<?php if ( $has_specs ) : ?>
					<div class="ss-yacht-specs-grid">
						<?php foreach ( $yacht['specs'] as $spec ) : ?>
						<div class="ss-yacht-spec-row">
							<span class="ss-yacht-spec-label"><?php echo esc_html( $spec['label'] ); ?></span>
							<span class="ss-yacht-spec-value"><?php echo esc_html( $spec['value'] ); ?></span>
						</div>
						<?php endforeach; ?>
					</div>
					<?php else : ?>
					<div class="ss-yacht-specs-grid">
						<?php if ( $yacht['year'] )    : ?><div class="ss-yacht-spec-row"><span class="ss-yacht-spec-label"><?php esc_html_e( 'Year', 'sailscanner-proposals' ); ?></span><span class="ss-yacht-spec-value"><?php echo absint( $yacht['year'] ); ?></span></div><?php endif; ?>
						<?php if ( $yacht['length_m'] ) : ?><div class="ss-yacht-spec-row"><span class="ss-yacht-spec-label"><?php esc_html_e( 'Length', 'sailscanner-proposals' ); ?></span><span class="ss-yacht-spec-value"><?php echo esc_html( $yacht['length_m'] ); ?>m</span></div><?php endif; ?>
						<?php if ( $yacht['cabins'] )   : ?><div class="ss-yacht-spec-row"><span class="ss-yacht-spec-label"><?php esc_html_e( 'Cabins', 'sailscanner-proposals' ); ?></span><span class="ss-yacht-spec-value"><?php echo absint( $yacht['cabins'] ); ?></span></div><?php endif; ?>
						<?php if ( $yacht['berths'] )   : ?><div class="ss-yacht-spec-row"><span class="ss-yacht-spec-label"><?php esc_html_e( 'Berths', 'sailscanner-proposals' ); ?></span><span class="ss-yacht-spec-value"><?php echo absint( $yacht['berths'] ); ?></span></div><?php endif; ?>
						<?php if ( $yacht['base_name'] ): ?><div class="ss-yacht-spec-row"><span class="ss-yacht-spec-label"><?php esc_html_e( 'Base', 'sailscanner-proposals' ); ?></span><span class="ss-yacht-spec-value"><?php echo esc_html( $yacht['base_name'] ); ?></span></div><?php endif; ?>
						<?php if ( $yacht['country'] )  : ?><div class="ss-yacht-spec-row"><span class="ss-yacht-spec-label"><?php esc_html_e( 'Country', 'sailscanner-proposals' ); ?></span><span class="ss-yacht-spec-value"><?php echo esc_html( $yacht['country'] ); ?></span></div><?php endif; ?>
					</div>
					<?php endif; ?>
				</section>
				<?php endif; ?>

				<!-- Pricing -->
				<?php
				$pricing_html = $has_prices ? SS_Proposal_Helpers::render_pricing_table( $yacht['prices'], false ) : '';
				if ( $pricing_html !== '' ) :
				?>
				<section class="ss-yacht-detail-section" id="pricing">
					<h2 class="ss-yacht-section-title">
						<span class="material-symbols-outlined" aria-hidden="true">payments</span>
						<?php esc_html_e( 'Pricing', 'sailscanner-proposals' ); ?>
					</h2>
					<?php echo $pricing_html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
				</section>
				<?php endif; ?>

				<!-- Equipment & Features -->
				<?php if ( $has_equip ) : ?>
				<section class="ss-yacht-detail-section" id="equipment">
					<h2 class="ss-yacht-section-title">
						<span class="material-symbols-outlined" aria-hidden="true">settings</span>
						<?php esc_html_e( 'Equipment & Features', 'sailscanner-proposals' ); ?>
					</h2>
					<div class="ss-proposal-yacht-equipment">
						<?php foreach ( $yacht['highlights'] as $h ) : ?>
						<span class="ss-proposal-yacht-pill"><?php echo esc_html( $h ); ?></span>
						<?php endforeach; ?>
					</div>
				</section>
				<?php endif; ?>

				<!-- Deck Plan -->
				<?php if ( $layout_image ) : ?>
				<section class="ss-yacht-detail-section" id="deck-plan">
					<h2 class="ss-yacht-section-title">
						<span class="material-symbols-outlined" aria-hidden="true">map</span>
						<?php esc_html_e( 'Deck Plan', 'sailscanner-proposals' ); ?>
					</h2>
					<div class="ss-yacht-deck-plan">
						<img src="<?php echo esc_url( $layout_image ); ?>"
							alt="<?php echo esc_attr( sprintf( __( '%s deck plan', 'sailscanner-proposals' ), $yacht['display_name'] ) ); ?>"
							loading="lazy" />
					</div>
				</section>
				<?php endif; ?>

				<!-- Mobile-only CTA (below all content) -->
				<div class="ss-yacht-cta-mobile">
					<?php if ( $wa_url ) : ?>
					<a href="<?php echo esc_url( $wa_url ); ?>" class="ss-proposal-btn ss-proposal-btn-whatsapp ss-yacht-cta-btn" target="_blank" rel="noopener noreferrer">
						<span class="material-symbols-outlined" aria-hidden="true">chat</span>
						<?php esc_html_e( 'Ask via WhatsApp', 'sailscanner-proposals' ); ?>
					</a>
					<?php endif; ?>
					<?php if ( $contact_email ) : ?>
					<a href="mailto:<?php echo esc_attr( $contact_email ); ?>?subject=<?php echo rawurlencode( sprintf( __( 'Enquiry: %s', 'sailscanner-proposals' ), $yacht['display_name'] ) ); ?>" class="ss-proposal-btn ss-proposal-btn-outline ss-yacht-cta-btn">
						<span class="material-symbols-outlined" aria-hidden="true">mail</span>
						<?php esc_html_e( 'Email us', 'sailscanner-proposals' ); ?>
					</a>
					<?php endif; ?>
				</div>

			</div><!-- /.ss-yacht-main -->

			<!-- RIGHT: sticky sidebar -->
			<aside class="ss-yacht-sidebar">
				<div class="ss-yacht-sidebar-card ss-proposal-card">

					<!-- Price summary -->
					<?php if ( $charter_price || $base_price ) : ?>
					<div class="ss-yacht-sidebar-price">
						<span class="ss-yacht-sidebar-price-label"><?php esc_html_e( 'Charter from', 'sailscanner-proposals' ); ?></span>
						<span class="ss-yacht-sidebar-price-amount">
							<?php echo esc_html( SS_Proposal_Helpers::decode_display_string( $charter_price ?: $base_price ) ); ?>
						</span>
						<?php if ( $charter_price && $base_price && $charter_price !== $base_price ) : ?>
						<span class="ss-yacht-sidebar-price-base"><?php printf( esc_html__( 'Base: %s', 'sailscanner-proposals' ), esc_html( SS_Proposal_Helpers::decode_display_string( $base_price ) ) ); ?></span>
						<?php endif; ?>
					</div>
					<hr class="ss-proposal-card-hr" />
					<?php endif; ?>

					<!-- Quick facts -->
					<div class="ss-yacht-sidebar-facts">
						<?php if ( $stat_cabins ) : ?>
						<div class="ss-yacht-sidebar-fact">
							<span class="material-symbols-outlined ss-yacht-sidebar-fact-icon" aria-hidden="true">bed</span>
							<span><?php echo esc_html( $stat_cabins ); ?> <?php esc_html_e( 'cabins', 'sailscanner-proposals' ); ?></span>
						</div>
						<?php endif; ?>
						<?php if ( $stat_berths ) : ?>
						<div class="ss-yacht-sidebar-fact">
							<span class="material-symbols-outlined ss-yacht-sidebar-fact-icon" aria-hidden="true">people</span>
							<span><?php echo esc_html( $stat_berths ); ?> <?php esc_html_e( 'berths', 'sailscanner-proposals' ); ?></span>
						</div>
						<?php endif; ?>
						<?php if ( $stat_length ) : ?>
						<div class="ss-yacht-sidebar-fact">
							<span class="material-symbols-outlined ss-yacht-sidebar-fact-icon" aria-hidden="true">straighten</span>
							<span><?php echo esc_html( $stat_length ); ?></span>
						</div>
						<?php endif; ?>
						<?php if ( $stat_year ) : ?>
						<div class="ss-yacht-sidebar-fact">
							<span class="material-symbols-outlined ss-yacht-sidebar-fact-icon" aria-hidden="true">calendar_today</span>
							<span><?php echo esc_html( $stat_year ); ?></span>
						</div>
						<?php endif; ?>
					<?php if ( ! empty( $_charter_first['base'] ) ) : ?>
					<div class="ss-yacht-sidebar-fact">
						<span class="material-symbols-outlined ss-yacht-sidebar-fact-icon" aria-hidden="true">location_on</span>
						<span><?php echo esc_html( $_charter_first['base'] ); ?></span>
					</div>
					<?php endif; ?>
					<?php if ( $sidebar_dates ) : ?>
					<div class="ss-yacht-sidebar-fact">
						<span class="material-symbols-outlined ss-yacht-sidebar-fact-icon" aria-hidden="true">event</span>
						<span><?php echo esc_html( $sidebar_dates ); ?></span>
					</div>
					<?php endif; ?>
					</div>

					<?php if ( $wa_url || $contact_email ) : ?>
					<hr class="ss-proposal-card-hr" />
					<div class="ss-yacht-sidebar-ctas">
						<?php if ( $wa_url ) : ?>
						<a href="<?php echo esc_url( $wa_url ); ?>" class="ss-proposal-btn ss-proposal-btn-whatsapp ss-yacht-cta-btn" target="_blank" rel="noopener noreferrer">
							<span class="material-symbols-outlined" aria-hidden="true">chat</span>
							<?php esc_html_e( 'Ask via WhatsApp', 'sailscanner-proposals' ); ?>
						</a>
						<?php endif; ?>
						<?php if ( $contact_email ) : ?>
						<a href="mailto:<?php echo esc_attr( $contact_email ); ?>?subject=<?php echo rawurlencode( sprintf( __( 'Enquiry: %s', 'sailscanner-proposals' ), $yacht['display_name'] ) ); ?>" class="ss-proposal-btn ss-proposal-btn-outline ss-yacht-cta-btn">
							<span class="material-symbols-outlined" aria-hidden="true">mail</span>
							<?php esc_html_e( 'Email us', 'sailscanner-proposals' ); ?>
						</a>
						<?php endif; ?>
					</div>
					<?php endif; ?>

					<!-- Section quick-nav -->
					<hr class="ss-proposal-card-hr" />
					<nav class="ss-yacht-sidebar-nav" aria-label="<?php esc_attr_e( 'Page sections', 'sailscanner-proposals' ); ?>">
						<p class="ss-yacht-sidebar-nav-heading"><?php esc_html_e( 'On this page', 'sailscanner-proposals' ); ?></p>
						<ul>
							<?php if ( $has_charter ) : ?>
							<li><a href="#charter-details" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">anchor</span><?php esc_html_e( 'Charter Details', 'sailscanner-proposals' ); ?></a></li>
							<?php endif; ?>
							<?php if ( $has_specs || $yacht['cabins'] || $yacht['year'] ) : ?>
							<li><a href="#specification" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">info</span><?php esc_html_e( 'Specification', 'sailscanner-proposals' ); ?></a></li>
							<?php endif; ?>
							<?php if ( $pricing_html ) : ?>
							<li><a href="#pricing" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">payments</span><?php esc_html_e( 'Pricing', 'sailscanner-proposals' ); ?></a></li>
							<?php endif; ?>
							<?php if ( $has_equip ) : ?>
							<li><a href="#equipment" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">settings</span><?php esc_html_e( 'Equipment & Features', 'sailscanner-proposals' ); ?></a></li>
							<?php endif; ?>
							<?php if ( $layout_image ) : ?>
							<li><a href="#deck-plan" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">map</span><?php esc_html_e( 'Deck Plan', 'sailscanner-proposals' ); ?></a></li>
							<?php endif; ?>
						</ul>
					</nav>

				</div><!-- /.ss-yacht-sidebar-card -->
			</aside><!-- /.ss-yacht-sidebar -->

		</div><!-- /.ss-yacht-layout -->
	</div><!-- /.ss-yacht-page-inner -->
</div><!-- /.ss-yacht-page -->

<script>
/* Gallery swap: shared with proposal page */
(function () {
	document.addEventListener('click', function (e) {
		var btn = e.target.closest('.ss-proposal-yacht-gallery-thumb');
		if (!btn) return;
		var galleryId = btn.dataset.gallery;
		var newSrc    = btn.dataset.src;
		if (!galleryId || !newSrc) return;
		var gallery = document.getElementById(galleryId);
		if (!gallery) return;
		var mainImg = gallery.querySelector('.ss-proposal-gallery-main-img');
		if (mainImg) mainImg.src = newSrc;
		gallery.querySelectorAll('.ss-proposal-yacht-gallery-thumb').forEach(function (t) {
			t.classList.remove('is-active');
		});
		btn.classList.add('is-active');
	});
})();
</script>

<?php
get_footer();
