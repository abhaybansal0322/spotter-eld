import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { PlanPage } from './components/PlanPage';
import './index.css';

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(
    <StrictMode>
      <PlanPage />
    </StrictMode>,
  );
}
