import React from 'react';

/**
 * PaginationControls
 * Reusable pagination UI used in SearchPage.
 *
 * Props:
 *  - offset
 *  - limit
 *  - total
 *  - on_page_change(new_offset)
 */
export default function PaginationControls({ offset, limit, total, on_page_change }) {
  const current_page = Math.floor(offset / limit) + 1;
  const total_pages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="flex items-center justify-center mt-4 gap-4">
      {offset > 5 ? (
        <button
          className="px-3 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm dark:bg-gray-700 dark:hover:bg-gray-600"
          onClick={() => on_page_change(0)}
        >
          First
        </button>
      ) : null}

      {offset === 0 ? (
        <button
          className="px-3 py-1 bg-gray-200 rounded text-sm text-gray-400 cursor-not-allowed dark:bg-gray-700 dark:text-gray-600"
          disabled
        >
          Prev
        </button>
      ) : (
        <button
          className="px-3 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm dark:bg-gray-700 dark:hover:bg-gray-600"
          onClick={() => on_page_change(Math.max(0, offset - limit))}
        >
          Prev
        </button>
      )}

      <span className="text-gray-700 text-sm font-semibold dark:text-gray-300">
        Page {current_page} of {total_pages}
      </span>

      {offset + limit >= total ? (
        <button
          className="px-3 py-1 bg-gray-200 rounded text-sm text-gray-400 cursor-not-allowed dark:bg-gray-700 dark:text-gray-600"
          disabled
        >
          Next
        </button>
      ) : (
        <button
          className="px-3 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm dark:bg-gray-700 dark:hover:bg-gray-600"
          onClick={() => on_page_change(offset + limit)}
        >
          Next
        </button>
      )}

      {offset < total - 5 * limit ? (
        <button
          className="px-3 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm dark:bg-gray-700 dark:hover:bg-gray-600"
          onClick={() => on_page_change(Math.max(0, total - (total % limit)))}
        >
          Last
        </button>
      ) : null}
    </div>
  );
}