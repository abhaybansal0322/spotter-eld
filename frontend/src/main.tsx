import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

// Mount point only. PlanPage is wired in when the components are built.
const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<StrictMode>{null}</StrictMode>);
}
