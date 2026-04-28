import { RouterProvider } from 'react-router-dom';
import { useEffect } from 'react';

import { router } from './app/router';
import { useAuthStore } from './store/authStore';

function App() {
  const hydrateAuth = useAuthStore((state) => state.hydrateAuth);

  useEffect(() => {
    hydrateAuth();
  }, [hydrateAuth]);

  return <RouterProvider router={router} />;
}

export default App;
