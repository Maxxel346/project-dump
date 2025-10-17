import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

// Contexts
import { useFavorites } from '../FavoriteContext';
import { useTheme } from '../ThemeContext';
import { useSearchTags } from '../SearchContext';

// API utilities
import {
  searchTagsByPrefix,
  searchTagsFuzzy,
  searchMediaByTags,
  getMediaPreviewUrl, // kept for MediaCard (imported there too, harmless)
  preflight,
  saveSearchHistory,
  getSearchHistory,
} from '../api';

// Components & hooks
import TagChip from '../components/TagChip';
import MediaCard from '../components/MediaCard';
import PaginationControls from '../components/PaginationControls';
import useDebounce from '../hooks/useDebounce';

/**
 * SearchPage
 * Main page component — responsible for composing search UI, tag selection, favorites sidebar, media results, and pagination.
 *
 * Debounced autocomplete: uses useDebounce to limit API calls for autosuggestions.
 */
export default function SearchPage() {
  const { theme, toggleTheme } = useTheme();

  const {
    includeTags,
    setIncludeTags,
    excludeTags,
    setExcludeTags,
    offset,
    setOffset,
    searchInput,
    setSearchInput,
    gridScroll,
    setGridScroll,
  } = useSearchTags();

  const grid_container_ref = useRef();

  // Autocomplete state
  const [autocomplete, set_autocomplete] = useState([]);
  const [loading_autocomplete, set_loading_autocomplete] = useState(false);
  const [show_dropdown, set_show_dropdown] = useState(false);

  const { favoriteTags } = useFavorites();

  const [show_tag_sidebar, set_show_tag_sidebar] = useState(false);

  // Media results
  const LIMIT = 30;
  const [media, set_media] = useState([]);
  const [total, set_total] = useState(0);
  const [loading_media, set_loading_media] = useState(false);

  const [favorite_only, set_favorite_only] = useState(false);
  const [search_history, set_search_history] = useState([]);
  const last_saved_signature_ref = useRef(null);

  const user_id = null; // derive from auth/localStorage if available in your app

  // Debounce the search input before calling autocomplete APIs
  const debounced_search_input = useDebounce(searchInput, 250);

  const search_box_ref = useRef();
  const grid_ref = useRef();

  const navigate = useNavigate();

  /************** helpers **************/
  function build_signature(include_tags, exclude_tags, favorite_only_flag) {
    return JSON.stringify({
      include: include_tags.map(t => t.value).sort(),
      exclude: exclude_tags.map(t => t.value).sort(),
      favoriteOnly: favorite_only_flag,
    });
  }

  const add_tag = (tag, type) => {
    if (type === 'IN') setIncludeTags([...includeTags, tag]);
    else setExcludeTags([...excludeTags, tag]);
    set_autocomplete([]);
    set_show_dropdown(false);
    setOffset(0);
  };

  const remove_tag = tag => {
    setIncludeTags(includeTags.filter(t => t.value !== tag.value));
    setExcludeTags(excludeTags.filter(t => t.value !== tag.value));
    setOffset(0);
  };

  function handle_media_card_click(id) {
    if (grid_container_ref.current) {
      setGridScroll(grid_container_ref.current.scrollTop);
    }
    navigate(`/detail/${id}`);
  }

  const handle_page_change = new_offset => {
    const total_pages = Math.max(1, Math.ceil(total / LIMIT));
    const max_offset = (total_pages - 1) * LIMIT;
    setOffset(Math.max(0, Math.min(new_offset, max_offset)));
  };

  /************** effects **************/

  // Load recent search history once
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const hist = await getSearchHistory(20, user_id);
        if (active) set_search_history(hist);
      } catch (e) {
        console.warn('Failed to fetch search history', e);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // Save scroll on unmount (back navigation)
  useEffect(() => {
    const node = grid_container_ref.current;
    return () => {
      if (node) setGridScroll(node.scrollTop);
    };
  }, [setGridScroll]);

  // Restore scroll position after media load (attempt frames)
  useEffect(() => {
    if (loading_media || !grid_container_ref.current || !media.length || !gridScroll) return;

    let cancelled = false;
    let try_count = 0;
    const node = grid_container_ref.current;

    function try_scroll() {
      if (cancelled) return;
      if (node.scrollHeight - node.clientHeight >= gridScroll) {
        node.scrollTop = gridScroll;
      } else if (try_count < 120) {
        try_count++;
        requestAnimationFrame(try_scroll);
      }
    }
    requestAnimationFrame(try_scroll);

    return () => {
      cancelled = true;
    };
  }, [loading_media, media.length, gridScroll]);

  // Fetch media when filters/pagination changes
  useEffect(() => {
    let running = true;
    set_loading_media(true);
    set_media([]);

    searchMediaByTags(
      includeTags.map(t => t.value),
      excludeTags.map(t => t.value),
      LIMIT,
      offset,
      favorite_only,
      user_id
    )
      .then(async data => {
        const items = data.items || [];

        if (items.length) {
          try {
            const ids = items.map(m => m.id);
            await preflight(ids);
          } catch (e) {
            console.error('Preflight error', e);
          }
        }

        if (!running) return;

        set_media(items);
        set_total(data.total || 0);
        set_loading_media(false);

        const signature = build_signature(includeTags, excludeTags, favorite_only);
        if (signature !== last_saved_signature_ref.current) {
          last_saved_signature_ref.current = signature;
          saveSearchHistory(
            includeTags.map(t => t.value),
            excludeTags.map(t => t.value),
            favorite_only,
            user_id
          ).catch(err => console.warn('Failed saving search history', err));
        }

        // Background fetch for next page (fire-and-forget)
        const next_offset = offset + LIMIT;
        (async () => {
          try {
            if (next_offset >= total) return;
            const next_data = await searchMediaByTags(
              includeTags.map(t => t.value),
              excludeTags.map(t => t.value),
              LIMIT,
              offset,
              favorite_only,
              user_id,
              true // cached only
            );
            const next_ids = (next_data.items || []).map(m => m.id);
            if (next_ids.length) {
              preflight(next_ids).catch(() => {});
            }
          } catch {
            // ignore
          }
        })();
      })
      .catch(() => {
        if (!running) return;
        set_media([]);
        set_total(0);
        set_loading_media(false);
      });

    return () => {
      running = false;
    };
  }, [includeTags, excludeTags, offset]); // kept as original

  // Autocomplete effect: uses debounced_search_input
  useEffect(() => {
    let active = true;
    const load_tags = async () => {
      if (!debounced_search_input || debounced_search_input.length < 2) {
        set_autocomplete([]);
        set_show_dropdown(false);
        return;
      }
      set_loading_autocomplete(true);

      let results = await searchTagsByPrefix(debounced_search_input, 15).catch(() => []);
      if (!results || !results.length) {
        results = await searchTagsFuzzy(debounced_search_input, 15).catch(() => []);
      }

      const chosen_ids = new Set([...includeTags.map(t => t.id), ...excludeTags.map(t => t.id)]);
      const chosen_values = new Set([...includeTags.map(t => t.value), ...excludeTags.map(t => t.value)]);
      const filtered = results.filter(t => !chosen_ids.has(t.id) && !chosen_values.has(t.value));

      if (active) set_autocomplete(filtered);
      set_show_dropdown(filtered.length > 0);
      set_loading_autocomplete(false);
    };

    load_tags();
    return () => {
      active = false;
    };
  }, [debounced_search_input, includeTags, excludeTags]);

  // Responsive grid columns
  const [cols, set_cols] = useState(2);
  useEffect(() => {
    const handle_resize = () => {
      if (grid_ref.current) {
        const width = grid_ref.current.offsetWidth;
        const possible_cols = Math.floor(width / 200);
        const clamped = Math.max(2, Math.min(possible_cols, 6));
        set_cols(clamped);
      }
    };
    handle_resize();
    window.addEventListener('resize', handle_resize);
    return () => window.removeEventListener('resize', handle_resize);
  }, []);

  // Click outside search box closes dropdown
  useEffect(() => {
    function handler(e) {
      if (search_box_ref.current && !search_box_ref.current.contains(e.target)) set_show_dropdown(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  /************** render **************/
  return (
    <div className="flex flex-col md:flex-row h-full min-h-screen">
      {/* SEARCH / FILTER SIDEBAR */}
      <div className="md:w-1/6 p-4 bg-white border-b md:border-b-0 md:border-r min-h-[170px] dark:bg-gray-800 dark:text-gray-100 dark:border-gray-700">
        <div ref={search_box_ref} className="relative mb-3">
          <label className="block font-semibold text-gray-700 mb-1 dark:text-gray-100">Search tags</label>
          <input
            className="w-full border rounded px-3 py-2 focus:outline-none focus:ring focus:border-blue-300 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 dark:focus:ring-blue-500 dark:focus:border-blue-500"
            type="text"
            value={searchInput}
            onChange={e => {
              setSearchInput(e.target.value);
              set_show_dropdown(true);
            }}
            placeholder="Type at least 2 letters..."
            onFocus={() => {
              if (searchInput.length >= 2) set_show_dropdown(true);
            }}
          />

          {show_dropdown && (
            <div className="absolute z-20 w-full mt-1 bg-white border shadow-lg rounded-lg max-h-64 overflow-auto dark:bg-gray-700">
              {loading_autocomplete && <div className="p-3 text-gray-500 text-sm">Loading…</div>}
              {!loading_autocomplete &&
                autocomplete.map(tag => (
                  <div key={tag.id} className="flex items-center justify-between px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-600">
                    <span className="text-gray-800 text-sm dark:text-gray-100">{tag.value}</span>
                    <span className="text-gray-400 text-xs">{tag.count} results</span>
                    <span>
                      <button className="px-2 py-1 text-xs bg-blue-500 rounded text-white hover:bg-blue-600" onClick={() => add_tag(tag, 'IN')}>IN</button>
                      <button className="ml-2 px-2 py-1 text-xs bg-red-500 rounded text-white hover:bg-red-600" onClick={() => add_tag(tag, 'EX')}>EX</button>
                    </span>
                  </div>
                ))}
              {!loading_autocomplete && autocomplete.length === 0 && debounced_search_input && debounced_search_input.length >= 2 && (
                <div className="p-3 text-gray-500 text-sm">No tags found.</div>
              )}
            </div>
          )}
        </div>

        <div className="mt-2 mb-2">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={favorite_only} onChange={e => { set_favorite_only(e.target.checked); setOffset(0); }} />
            <span className="text-sm">Show favorites only</span>
          </label>
        </div>

        <div className="mb-2">
          <span className="text-blue-600 font-semibold text-sm">Include:</span>
          <div className="mt-1 flex flex-wrap">
            {includeTags.length === 0 && <span className="text-gray-400 text-xs ml-1">None</span>}
            {includeTags.map(tag => <TagChip key={tag.id ?? tag.value} tag={tag} type="IN" on_remove={remove_tag} />)}
          </div>
        </div>

        <div>
          <span className="text-red-600 font-semibold text-sm">Exclude:</span>
          <div className="mt-1 flex flex-wrap">
            {excludeTags.length === 0 && <span className="text-gray-400 text-xs ml-1">None</span>}
            {excludeTags.map(tag => <TagChip key={tag.id ?? tag.value} tag={tag} type="EX" on_remove={remove_tag} />)}
          </div>
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between">
            <span className="font-semibold">Recent searches</span>
            <button className="text-xs text-blue-500" onClick={async () => {
              try {
                const hist = await getSearchHistory(50, user_id);
                set_search_history(hist);
              } catch(e) { console.warn(e) }
            }}>Refresh</button>
          </div>
          <div className="mt-2 max-h-40 overflow-auto">
            {search_history.length === 0 ? (
              <div className="text-xs text-gray-400">No recent searches</div>
            ) : (
              search_history.map(h => (
                <button key={h.id}
                  className="w-full text-left px-2 py-1 hover:bg-gray-100 rounded text-sm"
                  onClick={() => {
                    setIncludeTags((h.include_tags || []).map(v => ({ id: null, value: v })));
                    setExcludeTags((h.exclude_tags || []).map(v => ({ id: null, value: v })));
                    set_favorite_only(!!h.favorite_only);
                    setOffset(0);
                  }}
                >
                  <div className="flex justify-between">
                    <div className="truncate">
                      <span className="text-xs text-gray-600">IN:</span> {(h.include_tags||[]).join(', ')}{' '}
                      <span className="ml-1 text-xs text-gray-600">EX:</span> {(h.exclude_tags||[]).join(', ')}
                    </div>
                  </div>
                  {h.favorite_only && <div className="text-xs text-yellow-700">Favorites only</div>}
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Floating buttons */}
      <button
        className="fixed z-30 right-3 top-14 bg-gray-900 dark:bg-gray-100 dark:text-gray-900 text-gray-100 font-bold px-3 py-2 rounded-full shadow-lg md:right-6"
        style={{ transition: 'right 0.3s', marginTop: 8 }}
        onClick={toggleTheme}
      >
        {theme === 'dark' ? "🌙 Dark" : "☀️ Light"}
      </button>

      <button
        className="fixed z-30 right-3 top-3 bg-yellow-400 hover:bg-yellow-500 text-yellow-900 font-bold px-4 py-2 rounded-full shadow-lg md:right-6"
        onClick={()=>set_show_tag_sidebar(s => !s)}
        style={{ transition: 'right 0.3s' }}
      >
        ⭐ Favorite Tags
      </button>

      {/* Favorite tags sidebar */}
      <div
        className={`fixed top-0 right-0 h-full w-80 bg-white shadow-lg border-l transition-transform duration-300 z-40 dark:bg-gray-800 dark:text-gray-100 dark:border-gray-700
          ${show_tag_sidebar ? '' : 'translate-x-full'}`}
        style={{ maxWidth: 320, minWidth: 240 }}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <span className="font-semibold text-lg">⭐ Favorite Tags</span>
          <button className="text-xl text-gray-400 hover:text-gray-700" onClick={()=>set_show_tag_sidebar(false)}>&times;</button>
        </div>
        <div className="p-4 overflow-y-auto" style={{ maxHeight: "calc(100vh - 56px)" }}>
          {favoriteTags.length === 0 ? (
            <div className="text-gray-400 text-sm">No favorite tags yet.<br/>Right-click/long-press a tag to add.</div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {favoriteTags.map(tag => (
                <button
                  key={tag.id}
                  className="bg-yellow-100 text-yellow-800 px-3 py-1 rounded-full text-xs mr-2 mb-2 border font-medium focus:ring-2 focus:ring-yellow-300 transition shadow hover:bg-yellow-200"
                  title="Click to add to filters"
                  onClick={() => {
                    add_tag(tag, "IN");
                    set_show_tag_sidebar(false);
                  }}
                >
                  {tag.value}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Media grid */}
      <div className="flex-1 p-4 overflow-auto bg-gray-50 dark:bg-gray-900" ref={grid_container_ref}>
        {loading_media ? (
          <div className="flex items-center justify-center w-full h-72 text-gray-500">Loading media…</div>
        ) : (
          <>
            <PaginationControls offset={offset} limit={LIMIT} total={total} on_page_change={handle_page_change} />

            <div
              ref={grid_ref}
              className="grid gap-2 auto-rows-fr"
              style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
            >
              {media && media.length > 0 ? (
                media.map(m => (
                  <MediaCard key={m.id} media={m} on_click={() => handle_media_card_click(m.id)} />
                ))
              ) : (
                <div className="col-span-full w-full text-center text-gray-400 py-8 text-lg">No results found.</div>
              )}
            </div>

            <PaginationControls offset={offset} limit={LIMIT} total={total} on_page_change={handle_page_change} />
            <div className="mt-8" />
          </>
        )}
      </div>
    </div>
  );
}