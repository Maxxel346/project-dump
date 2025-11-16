// DetailPage.js - updated UI + abortable API usage
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchMediaWithTags,
  fetchRecommendations,
  fetchMediaBatch,
  getMediaPreviewUrl,
  getMediaFullUrl,
} from "../api";
import { useNavigate, useParams } from "react-router-dom";
import { useFavorites } from "../FavoriteContext";

/* -----------------------
   Utilities
   ----------------------- */
/** Convert numeric type to string */
function type_str(x) {
  switch (x) {
    case 0: return "Image";
    case 1: return "Video";
    default: return "-";
  }
}

/** Safe tag value extraction */
function safe_tag_value(tag) {
  return (tag && (tag.value || tag)) || "";
}

/* -----------------------
   Hooks / small utilities
   ----------------------- */
/**
 * Hook: IntersectionObserver boolean for a ref -> in_view
 * Fires once (unobserves on first intersect) to reduce repeated toggles
 */
function useInView(ref, options = {}) {
  const [in_view, set_in_view] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          set_in_view(true);
          observer.unobserve(entry.target);
        }
      });
    }, options);
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, options]);

  return in_view;
}

/* -----------------------
   Icons
   ----------------------- */
/** Accessible heart icon (SVG) */
function HeartIcon({ filled = false, class_name = "", title = "" }) {
  // Inline small accessible SVG
  return (
    <svg
      className={class_name}
      viewBox="0 0 24 24"
      width="18"
      height="18"
      aria-hidden={title ? "false" : "true"}
      role={title ? "img" : "presentation"}
    >
      {title ? <title>{title}</title> : null}
      <path
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.2"
        d="M12.1 21s-7.2-4.6-9.1-7.3C-1.2 8.4 5.2 3 8.8 5.3 10.5 6.5 12 8.6 12 8.6s1.6-2.1 3.2-3.3C18.8 3 25.2 8.4 21 13.7c-1.9 2.7-9.9 7.3-9.9 7.3z"
      />
    </svg>
  );
}

/* -----------------------
   Components
   ----------------------- */

/** Favorite toggle button - accessible, large touch target, aria-pressed */
function FavoriteToggleButton({ is_fav, on_toggle, class_name = "" }) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        on_toggle();
      }}
      aria-pressed={is_fav}
      className={`${class_name} w-11 h-11 flex items-center justify-center rounded-full focus:outline-none`}
      // ensure >=44px touch target: w-11/h-11 ~ 44px (depends on tailwind)
    >
      <HeartIcon filled={is_fav} class_name={is_fav ? "text-red-500" : "text-gray-400"} title={is_fav ? "Favorited" : "Add to favorites"} />
    </button>
  );
}

/**
 * MediaCardPreview: preview area for a card.
 * - Lazy loads preview image
 * - defers video src until in view (IntersectionObserver)
 */
function MediaCardPreview({ media, video_preview, set_video_preview }) {
  const [img_error, set_img_error] = useState(false);
  const ref = useRef(null);
  const is_visible = useInView(ref, { rootMargin: "160px" });

  // Only set video preview src when card in view
  const preview_video_src = is_visible && media.type === 1 ? getMediaPreviewUrl(media, "video") : "";

  if (media.type === 1) {
    return (
      <a
        href={`/detail/${media.id}`}
        className="w-full aspect-square relative group block"
        onMouseEnter={() => set_video_preview(true)}
        onMouseLeave={() => set_video_preview(false)}
        ref={ref}
      >
        {video_preview ? (
          <video
            src={preview_video_src}
            autoPlay
            muted
            loop
            preload="metadata"
            className="w-full aspect-square object-cover rounded-t"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <img
            src={getMediaPreviewUrl(media, "image")}
            alt={media.id}
            loading="lazy"
            className="w-full aspect-square object-cover rounded-t"
            onError={() => set_img_error(true)}
          />
        )}
        <span className="absolute top-1 right-1 bg-gray-800 text-white text-xs px-2 py-0.5 rounded opacity-75">🎬</span>
      </a>
    );
  }

  if (media.type === 0) {
    return (
      <a href={`/detail/${media.id}`} className="w-full aspect-square relative group block" ref={ref}>
        {!img_error ? (
          <img
            src={getMediaPreviewUrl(media, "image")}
            alt={media.id}
            loading="lazy"
            className="w-full aspect-square object-cover rounded-t"
            onError={() => set_img_error(true)}
          />
        ) : (
          <div className="w-full aspect-square bg-gray-200 text-gray-600 flex items-center justify-center text-sm rounded-t">❌ Error loading</div>
        )}
      </a>
    );
  }

  return (
    <a href={`/detail/${media.id}`} className="w-full aspect-square relative group block" ref={ref}>
      <div className="w-full h-24 bg-gray-200 text-gray-600 flex items-center justify-center text-sm rounded-t">?</div>
    </a>
  );
}

/**
 * TagBadge (keeps same behavior)
 */
function TagBadge({ tag }) {
  const { favoriteTags, favoriteTag, unfavoriteTag } = useFavorites();
  const tag_val = safe_tag_value(tag);
  const fav_obj = favoriteTags.find((t) => t.value === tag_val);
  const is_fav = Boolean(fav_obj);

  function handle_toggle(e) {
    e.preventDefault();
    e.stopPropagation();
    if (is_fav) unfavoriteTag(fav_obj.id);
    else favoriteTag({ id: tag.id ?? null, value: tag_val });
  }

  return (
    <span className="inline-flex items-center bg-blue-100 text-blue-700 rounded-full px-2 py-1 text-xs mr-2 mb-2">
      <span>{tag_val}</span>
      <button className="ml-2 focus:outline-none" aria-label={is_fav ? "Remove tag from favorites" : "Add tag to favorites"} onClick={handle_toggle}>
        <span className={is_fav ? "text-yellow-500" : "text-gray-300"} style={{ fontSize: "1rem" }}>★</span>
      </button>
    </span>
  );
}

/**
 * Skeleton card placeholder used while recommendations load.
 */
function SkeletonCard() {
  return (
    <div className="bg-white rounded-lg border shadow animate-pulse p-2 h-0" style={{ paddingBottom: "100%" /* aspect square preserved */ }}>
      <div className="w-full h-full bg-gray-200 rounded"></div>
    </div>
  );
}

/**
 * MediaCard - memoized to avoid unnecessary re-renders.
 * Props: media, onClick, is_fav, on_toggle_fav, is_active (to show selected state)
 */
const MediaCard = React.memo(function MediaCard({ media, onClick, is_fav, on_toggle_fav, is_active }) {
  const [video_preview, set_video_preview] = useState(false);

  // selected/active state style
  const active_class = is_active ? "ring-2 ring-blue-400" : "";

  return (
    <div
      onClick={onClick}
      className={`cursor-pointer bg-white shadow rounded-lg border flex flex-col items-center hover:ring-2 hover:ring-blue-400 transition transform hover:scale-105 ${active_class} dark:bg-gray-800 dark:border-gray-700`}
      role="button"
      tabIndex={0}
      onKeyPress={(e) => { if (e.key === "Enter") onClick(); }}
    >
      <div className="w-full aspect-square relative">
        <MediaCardPreview media={media} video_preview={video_preview} set_video_preview={set_video_preview} />
        <div className="absolute top-2 left-2 z-10">
          <FavoriteToggleButton is_fav={is_fav} on_toggle={on_toggle_fav} class_name="bg-white dark:bg-gray-800 shadow" />
        </div>
      </div>
    </div>
  );
}, (prev, next) => {
  // shallow compare id & is_fav & onClick identity
  return prev.media.id === next.media.id && prev.is_fav === next.is_fav && prev.onClick === next.onClick && prev.is_active === next.is_active;
});

/* -----------------------
   DetailPage main component
   ----------------------- */
export default function DetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { favoriteMediaIds, favoriteMedia, unfavoriteMedia } = useFavorites();

  const [media, set_media] = useState(null);
  const [media_error, set_media_error] = useState(false);
  const [recommend_ids, set_recommend_ids] = useState([]);
  const [recommend_media, set_recommend_media] = useState([]);
  const [show_all, set_show_all] = useState(false);
  const [recommend_loading, set_recommend_loading] = useState(false);

  const is_fav = media && favoriteMediaIds.includes(media.id);

  // Keep refs to controllers for cleanup
  const media_controller_ref = useRef(null);
  const recommend_controller_ref = useRef(null);
  const batch_controller_ref = useRef(null);
  const rec_timer_ref = useRef(null);
  useEffect(() => {
    const link = document.querySelector("link[rel~='icon']");
    link.href = "/icons/loop.png";  // path is still relative to public/
  }, []);
  // Helper: create a stable toggle function for item id (memoized via useCallback)
  const make_toggle_for = useCallback((id_to_toggle) => {
    return () => {
      if (favoriteMediaIds.includes(id_to_toggle)) unfavoriteMedia(id_to_toggle);
      else favoriteMedia(id_to_toggle);
    };
  }, [favoriteMediaIds, favoriteMedia, unfavoriteMedia]);

  // Fetch media & schedule recommendations (with AbortController)
  useEffect(() => {
    // Reset state on id change
    set_media(null);
    set_media_error(false);
    set_recommend_ids([]);
    set_recommend_media([]);
    set_show_all(false);
    set_recommend_loading(false);

    // Abort previous controllers if present
    if (media_controller_ref.current) {
      media_controller_ref.current.abort();
      media_controller_ref.current = null;
    }
    if (recommend_controller_ref.current) {
      recommend_controller_ref.current.abort();
      recommend_controller_ref.current = null;
    }
    if (batch_controller_ref.current) {
      batch_controller_ref.current.abort();
      batch_controller_ref.current = null;
    }
    if (rec_timer_ref.current) {
      clearTimeout(rec_timer_ref.current);
      rec_timer_ref.current = null;
    }

    const media_controller = new AbortController();
    media_controller_ref.current = media_controller;

    // Fetch main media (pass signal for abortability)
    fetchMediaWithTags(id, { signal: media_controller.signal })
      .then((res) => set_media(res))
      .catch((err) => {
        if (err && err.name === "AbortError") {
          // ignore
          return;
        }
        set_media_error(true);
      })
      .finally(() => {
        // Keep original behavior: wait ~1s before fetching recommendations
        rec_timer_ref.current = setTimeout(() => {
          // prepare for recommendations
          set_recommend_ids([]);
          set_recommend_media([]);
          set_recommend_loading(true);

          const rec_controller = new AbortController();
          recommend_controller_ref.current = rec_controller;

          fetchRecommendations(id, { signal: rec_controller.signal })
            .then((arr) => set_recommend_ids(arr || []))
            .catch((err) => {
              if (err && err.name === "AbortError") return;
              set_recommend_ids([]);
            })
            .finally(() => {
              set_recommend_loading(false);
            });
        }, 1000);
      });

    // Cleanup on unmount or id change
    return () => {
      if (media_controller_ref.current) {
        media_controller_ref.current.abort();
        media_controller_ref.current = null;
      }
      if (recommend_controller_ref.current) {
        recommend_controller_ref.current.abort();
        recommend_controller_ref.current = null;
      }
      if (batch_controller_ref.current) {
        batch_controller_ref.current.abort();
        batch_controller_ref.current = null;
      }
      if (rec_timer_ref.current) {
        clearTimeout(rec_timer_ref.current);
        rec_timer_ref.current = null;
      }
    };
  }, [id, favoriteMediaIds, favoriteMedia, unfavoriteMedia]); // favorites included because fav toggles are allowed; not strictly necessary for fetch

  // When recommend IDs change or show_all toggles, fetch batch of details (abortable)
  useEffect(() => {
    // Cancel any prior batch controller
    if (batch_controller_ref.current) {
      batch_controller_ref.current.abort();
      batch_controller_ref.current = null;
    }

    if (!recommend_ids || !recommend_ids.length) {
      set_recommend_media([]);
      return;
    }

    const n = show_all ? recommend_ids.length : Math.ceil(recommend_ids.length / 2);
    const show_ids = recommend_ids.slice(0, n);
    const batch_controller = new AbortController();
    batch_controller_ref.current = batch_controller;

    fetchMediaBatch(show_ids, { signal: batch_controller.signal })
      .then((arr) => set_recommend_media((arr || []).filter(Boolean)))
      .catch((err) => {
        if (err && err.name === "AbortError") return;
        set_recommend_media([]);
      });

    return () => {
      if (batch_controller_ref.current) {
        batch_controller_ref.current.abort();
        batch_controller_ref.current = null;
      }
    };
  }, [recommend_ids, show_all]);

  if (media_error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-red-600 text-lg">Not found</div>
      </div>
    );
  }
  if (!media) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-500 text-lg">Loading…</div>
      </div>
    );
  }

  // Toggle favorite for main media
  function handle_media_fav_toggle() {
    if (is_fav) unfavoriteMedia(media.id);
    else favoriteMedia(media.id);
  }

  function handle_back() {
    if (window.history.state && window.history.state.idx > 0) navigate(-1);
    else navigate("/");
  }

  // Number of skeletons to show (same layout as visible items)
  const visible_count = show_all ? (recommend_ids.length || 6) : Math.ceil((recommend_ids.length || 6) / 2);

  return (
    <div className="min-h-screen dark:bg-gray-900 center p-4">
      <div className="max-w-5xl mx-auto bg-white rounded-lg shadow-lg p-6 dark:bg-gray-800 dark:text-gray-100">
        <button onClick={handle_back} className="mb-4 px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm dark:bg-blue-600 dark:hover:bg-blue-700" aria-label="Back to search">
          &larr; Back to search
        </button>

        <h2 className="text-2xl font-semibold mb-4">Media Detail</h2>

        <div className="w-full mb-3">
          {media.type === 0 ? (
            <img
              src={getMediaFullUrl(media)}
              alt={media.id}
              className="w-full object-contain border rounded"
              onError={e => { e.target.src = ''; }}
              loading="lazy"
            />
          ) : media.type === 1 ? (
            <video controls src={getMediaFullUrl(media, "video")} poster={getMediaPreviewUrl(media)} className="w-full object-contain border rounded" preload="metadata">
              Sorry, your browser does not support video.
            </video>
          ) : (
            <div className="w-full h-60 bg-gray-200 text-gray-600 flex items-center justify-center text-sm rounded">(unsupported)</div>
          )}
        </div>

        {/* METADATA */}
        <div className="mb-3 divide-y divide-gray-200 dark:divide-gray-700">
          <div className="pb-3">
            <dl className="flex flex-wrap">
              <dt className="font-bold w-1/2 text-sm">ID:</dt>
              <dd className="w-1/2 text-sm mb-1">{media.id}</dd>

              <dt className="font-bold w-1/2 text-sm">Posted:</dt>
              <dd className="w-1/2 text-sm mb-1">{media.posted}</dd>

              <dt className="font-bold w-1/2 text-sm">Likes:</dt>
              <dd className="w-1/2 text-sm mb-1">❤️ {media.likes}</dd>

              <dt className="font-bold w-1/2 text-sm">Type:</dt>
              <dd className="w-1/2 text-sm mb-1">{type_str(media.type)}</dd>
            </dl>
          </div>

          {/* Favorite toggle */}
          <div className="pt-3">
            <FavoriteToggleButton is_fav={is_fav} on_toggle={handle_media_fav_toggle} class_name="bg-white dark:bg-gray-700 shadow border" />
          </div>
        </div>

        {/* Tags */}
        <div className="mb-3">
          <span className="font-bold text-sm">Tags:</span>
          <div className="flex flex-wrap mt-1">
            {media.tags.map(tagObj => <TagBadge key={tagObj.id ?? tagObj.value} tag={tagObj} />)}
          </div>
        </div>

        {/* Source */}
        <div className="mb-3 mt-3">
          <span className="font-bold text-sm">Source:</span>
          <div className="text-sm">{media.source}</div>
        </div>

        {/* --- RECOMMENDATIONS --- */}
        <div className="mt-8">
          <h3 className="font-semibold text-lg mb-2">Recommended Media</h3>

          {recommend_loading && recommend_media.length === 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {Array.from({ length: visible_count }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : recommend_media.length === 0 ? (
            <div className="text-gray-400 mb-2">No recommendations.</div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {recommend_media.map(m => (
                <MediaCard
                  key={m.id}
                  media={m}
                  onClick={() => navigate(`/detail/${m.id}`)}
                  is_fav={favoriteMediaIds.includes(m.id)}
                  on_toggle_fav={make_toggle_for(m.id)}
                  is_active={String(m.id) === String(media.id)}
                />
              ))}
            </div>
          )}

          {recommend_ids.length > Math.ceil(recommend_ids.length / 2) && !show_all &&
            <button className="mt-3 px-3 py-1 rounded bg-blue-500 text-white hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700" onClick={() => set_show_all(true)}>
              Show More
            </button>
          }
        </div>
      </div>
    </div>
  );

}
