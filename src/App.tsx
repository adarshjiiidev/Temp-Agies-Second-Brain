import React from 'react';
import { OSProvider } from './lib/store';
import { TopBar } from './components/TopBar';
import { Desktop } from './components/Desktop';
import { Dock } from './components/Dock';

export const App: React.FC = () => {
  return (
    <OSProvider>
      <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#0a0a0c] text-[#f4f4f5] select-none font-sans">
        <TopBar />
        <Desktop />
        <Dock />
      </div>
    </OSProvider>
  );
};

export default App;
