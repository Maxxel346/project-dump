import React, { createContext, useContext, useState, useEffect } from "react";

const KEY = "searchTagsV1";

const defaultValue = {
  includeTags: [],
  excludeTags: [],
  setIncludeTags: () => {},
  setExcludeTags: () => {},
  offset: 0,
  setOffset: () => {},
  searchInput: "",
  setSearchInput: () => {},
  gridScroll: 0,
  setGridScroll: () => {},
};

const SearchContext = createContext(defaultValue);

export function SearchProvider({ children }) {
  const [includeTags, setIncludeTags] = useState([]);
  const [excludeTags, setExcludeTags] = useState([]);
  const [offset, setOffset] = useState(0); // <--- Add this
  const [searchInput, setSearchInput] = useState(""); // <--- And this
  const [gridScroll, setGridScroll] = useState(0); // <--- And this

  // On mount, restore from sessionStorage
  useEffect(() => {
    const data = sessionStorage.getItem(KEY);
    if (data) {
      try {
        const json = JSON.parse(data);
        setIncludeTags(json.includeTags || []);
        setExcludeTags(json.excludeTags || []);
        setOffset(json.offset || 0);
        setSearchInput(json.searchInput || "");
        setGridScroll(json.gridScroll || 0);
      } catch {}
    }
  }, []);

  // On change, persist (all properties)
  useEffect(() => {
    sessionStorage.setItem(KEY, JSON.stringify({
      includeTags,
      excludeTags,
      offset,
      searchInput,
      gridScroll
    }));
  }, [includeTags, excludeTags, offset, searchInput, gridScroll]);

  return (
    <SearchContext.Provider value={{
      includeTags, setIncludeTags,
      excludeTags, setExcludeTags,
      offset, setOffset,
      searchInput, setSearchInput,
      gridScroll, setGridScroll
    }}>
      {children}
    </SearchContext.Provider>
  );
}

export function useSearchTags() {
  return useContext(SearchContext);
}