import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import SearchPage from "./components/SearchPage";
import DetailPage from "./components/DetailPage";
import { SearchProvider } from './SearchContext';
import { FavoriteProvider } from "./FavoriteContext";
import { ThemeProvider } from './ThemeContext';

export default function App() {
  return (
    <ThemeProvider>
      <FavoriteProvider>
        <SearchProvider>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/detail/:id" element={<DetailPage />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </SearchProvider>
      {/* ... old code ... */}
    </FavoriteProvider>
  </ThemeProvider>
  );
  // );
}