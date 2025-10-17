import React from 'react';
import { useFavorites } from '../FavoriteContext';

/**
 * TagChip
 * Small UI element representing a chosen tag with remove button and favorite toggle.
 *
 * Props:
 *  - tag: { id, value, ... }
 *  - type: 'IN' | 'EX'
 *  - on_remove: callback(tag)
 */
export default function TagChip({ tag, type, on_remove }) {
  const { favoriteTags, favoriteTag, unfavoriteTag } = useFavorites();

  const is_fav = favoriteTags.some(t => t.id === tag.id);

  // Simple long-press detection for mobile favoriting (0.6s)
  let press_timer = null;
  const handle_mouse_down = e => {
    if (e.type !== 'mousedown' && e.type !== 'touchstart') return;
    press_timer = setTimeout(() => {
      if (is_fav) unfavoriteTag(tag.id);
      else favoriteTag(tag);
    }, 600);
  };
  const clear_press = () => {
    if (press_timer) clearTimeout(press_timer);
    press_timer = null;
  };

  return (
    <span
      onContextMenu={e => {
        e.preventDefault();
        if (is_fav) unfavoriteTag(tag.id);
        else favoriteTag(tag);
      }}
      onMouseDown={handle_mouse_down}
      onMouseUp={clear_press}
      onMouseLeave={clear_press}
      onTouchStart={handle_mouse_down}
      onTouchEnd={clear_press}
      className={`inline-flex items-center px-2 py-1 mr-2 mb-2 text-xs font-medium text-white rounded-full
        ${type === 'IN' ? 'bg-blue-500' : 'bg-red-500'} 
        ${type === 'IN' ? 'hover:bg-blue-600' : 'hover:bg-red-600'}
        relative select-none cursor-pointer`}
      title="Right-click or long-press to (un)favorite"
    >
      {tag.value}
      <button
        onClick={e => {
          e.stopPropagation();
          on_remove(tag);
        }}
        className="ml-1 text-white hover:text-yellow-100 focus:outline-none"
        tabIndex={-1}
        aria-label="remove"
      >
        &times;
      </button>
      <span className={`ml-2 text-yellow-400 text-xs${is_fav ? '' : ' opacity-20'}`} title={is_fav ? 'Favorite tag' : 'Not in favorites'}>
        ★
      </span>
    </span>
  );
}