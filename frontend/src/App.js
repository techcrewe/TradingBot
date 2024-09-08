import React, { useState } from 'react';
import SignalsTable from './components/SignalsTable';
import TradingViewWidget from './components/TradingViewWidget';

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState('GBPUSD');

  const handleSymbolSelect = (symbol) => {
    setSelectedSymbol(symbol);
  };

  return (
    <div className="App">
      <h1>Trading Bot Dashboard</h1>
      <TradingViewWidget symbol={selectedSymbol} />
      <SignalsTable onSymbolSelect={handleSymbolSelect} />
    </div>
  );
}

export default App;