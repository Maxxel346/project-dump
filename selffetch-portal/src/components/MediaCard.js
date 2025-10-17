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
          className="absolute top-2 left-2 bg-white rounded-full p-1 shadow hover:bg-red-100 z-10 dark:bg-gray-800 dark:hover:bg-red-700"
          onClick={e => {
            e.stopPropagation();
            is_favorite ? unfavoriteMedia(media.id) : favoriteMedia(media.id);
          }}
          aria-label={is_favorite ? 'Remove from favorites' : 'Add to favorites'}
        >
          <span className={is_favorite ? 'text-red-500 text-lg' : 'text-gray-400 text-lg'}>♥</span>
        </button>
      </a>
    </div>
  );
}