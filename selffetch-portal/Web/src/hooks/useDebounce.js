import { useState, useEffect } from 'react';

/**
 * useDebounce hook
 * Returns a debounced value that updates only after "delay" milliseconds
 * of inactivity have passed. Useful to reduce API calls for rapidly changing
 * inputs (autocomplete, search boxes, etc.).
 *
 * @param {*} value - input value to debounce
 * @param {number} delay - debounce delay in ms
 * @returns debounced value
 */
export default function useDebounce(value, delay = 250) {
  const [debounced_value, set_debounced_value] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => set_debounced_value(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);

  return debounced_value;
}