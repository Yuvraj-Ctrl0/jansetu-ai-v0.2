import React from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/anek-latin/wdth.css';
import '@fontsource/anek-devanagari/600.css';
import '@fontsource/anek-devanagari/800.css';
import '@fontsource/mukta/400.css';
import '@fontsource/mukta/500.css';
import '@fontsource/mukta/600.css';
import '@fontsource/mukta/700.css';
import App from './App';
import './style.css';

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
