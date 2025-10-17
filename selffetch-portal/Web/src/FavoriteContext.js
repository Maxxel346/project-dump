import React, { createContext, useContext, useEffect, useState } from "react";
import {
  getFavoriteMedia,
  getFavoriteTags,
  addFavoriteMedia,
  removeFavoriteMedia,
  addFavoriteTag,
  removeFavoriteTag
} from "./api";

const FavoriteContext = createContext();

export function useFavorites() {
  return useContext(FavoriteContext);
}

export function FavoriteProvider({ children }) {
  const [favoriteMediaIds, setFavoriteMediaIds] = useState([]);
  const [favoriteTags, setFavoriteTags] = useState([]); // [{id,value}]

  const refresh = async () => {
    try {
      const [media, tags] = await Promise.all([
        getFavoriteMedia(),
        getFavoriteTags()
      ]);
      setFavoriteMediaIds(media.map(m => m.media_id));
      setFavoriteTags(tags);
    } catch (e) {}
  };

  // load on mount
  useEffect(() => { refresh(); }, []);

  // Favorite / unfavorite functions
  const favoriteMedia = async (media_id) => {
    try {
      await addFavoriteMedia(media_id);
      setFavoriteMediaIds(ids => ids.includes(media_id) ? ids : [...ids, media_id]);
    } catch (e) {}
  };
  const unfavoriteMedia = async (media_id) => {
    try {
      await removeFavoriteMedia(media_id);
      setFavoriteMediaIds(ids => ids.filter(id => id !== media_id));
    } catch (e) {}
  };
  const favoriteTag = async (tag) => {
    try {
      await addFavoriteTag(tag);
      setFavoriteTags(tags => tags.some(t=>t.id===tag.id) ? tags : [...tags, tag]);
    } catch (e) {}
  };
  const unfavoriteTag = async (tag_id) => {
    try {
      await removeFavoriteTag(tag_id);
      setFavoriteTags(tags => tags.filter(t=>t.id!==tag_id));
    } catch (e) {}
  };

  const value = {
    favoriteMediaIds,
    favoriteTags,
    refresh,
    favoriteMedia,
    unfavoriteMedia,
    favoriteTag,
    unfavoriteTag
  };

  return (
    <FavoriteContext.Provider value={value}>
      {children}
    </FavoriteContext.Provider>
  );
}