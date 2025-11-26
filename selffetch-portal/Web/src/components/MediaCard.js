import React, { useState } from 'react';
import { useFavorites } from '../FavoriteContext';
import { getMediaPreviewUrl } from '../api';

/**
 * MediaCard
 * Render a media tile (image or video preview). Clicking favorite heart toggles favorite.
 *
 * Props:
 *  - media: media object from API (id, type, ...)
 *  - on_click: callback to navigate/open detail
 */

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


export default function MediaCard({ media, on_click }) {
  const { favoriteMediaIds, favoriteMedia, unfavoriteMedia } = useFavorites();
  const [img_error, set_img_error] = useState(false);
  const [video_preview, set_video_preview] = useState(false);

  const is_favorite = favoriteMediaIds.includes(media.id);

  return (
    <div
      onClick={on_click}
      className="cursor-pointer bg-white shadow rounded-lg border flex flex-col items-center hover:ring-2 hover:ring-blue-400 transition dark:bg-gray-800 dark:border-gray-700"
    >
      <a
        href={`/detail/${media.id}`}
        className="w-full aspect-square relative group"
        onMouseEnter={() => set_video_preview(true)}
        onMouseLeave={() => set_video_preview(false)}
      >
        {media.type === 1 ? (
          video_preview ? (
            <video
              src={getMediaPreviewUrl(media, 'video')}
              autoPlay
              muted
              loop
              className="w-full aspect-square object-cover rounded-t"
              onClick={e => e.stopPropagation()}
            />
          ) : (
            <img
              src={getMediaPreviewUrl(media, 'image')}
              alt={media.id}
              className="w-full aspect-square object-cover rounded-t"
              onError={() => set_img_error(true)}
            />
          )
        ) : media.type === 0 ? (
          !img_error ? (
            <img
              src={getMediaPreviewUrl(media, 'image')}
              alt={media.id}
              className="w-full aspect-square object-cover rounded-t"
              onError={() => set_img_error(true)}
            />
          ) : (
            <div className="w-full aspect-square bg-gray-200 text-gray-600 flex items-center justify-center text-sm rounded-t">
              ❌ Error loading
            </div>
          )
        ) : (
          <div className="w-full h-24 bg-gray-200 text-gray-600 flex items-center justify-center text-sm rounded-t">?</div>
        )}

        {media.type === 1 && (
          <span className="absolute top-1 right-1 bg-gray-800 text-white text-xs px-2 py-0.5 rounded opacity-75">🎬</span>
        )}

        <button
          className="absolute top-2 left-2 bg-white rounded-full flex items-center justify-center w-11 h-11 shadow hover:bg-red-100 z-30 dark:bg-gray-800 dark:hover:bg-red-700"
          onClick={e => {
            e.preventDefault();  // THIS prevents navigation from <a>
            e.stopPropagation(); // prevent bubbling up to other handlers
            is_favorite ? unfavoriteMedia(media.id) : favoriteMedia(media.id);
          }}
          aria-label={is_favorite ? 'Remove from favorites' : 'Add to favorites'}
          type="button"
        >
          <HeartIcon filled={is_favorite} class_name={is_favorite ? "text-red-500" : "text-gray-400"} title={is_favorite ? "Favorited" : "Add to favorites"} />
        </button>
      </a>
    </div>
  );
}