import React, { useState, useEffect } from 'react';
import axios from 'axios';

const SignalsTable = ({ onSymbolSelect }) => {
  const [signals, setSignals] = useState([]);

  useEffect(() => {
    const fetchSignals = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/signals');
        setSignals(response.data);
      } catch (error) {
        console.error('Error fetching signals:', error);
      }
    };

    fetchSignals();
    const interval = setInterval(fetchSignals, 60000); // Refresh every minute

    return () => clearInterval(interval);
  }, []);

  const handleRowClick = (symbol, chartSymbol) => {
    onSymbolSelect(symbol, chartSymbol);
  };

  return (
    <div className="signals-table">
      <h2>Signals</h2>
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr>
            <th style={{ border: '1px solid #ddd', padding: '8px' }}>Symbol</th>
            <th style={{ border: '1px solid #ddd', padding: '8px' }}>Date</th>
            <th style={{ border: '1px solid #ddd', padding: '8px' }}>Entry</th>
            <th style={{ border: '1px solid #ddd', padding: '8px' }}>Stop Loss</th>
            <th style={{ border: '1px solid #ddd', padding: '8px' }}>Take Profit</th>
            <th style={{ border: '1px solid #ddd', padding: '8px' }}>D Exp</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((signal, index) => (
            <tr key={index} onClick={() => handleRowClick(signal.symbol, signal.chart_symbol)} style={{ cursor: 'pointer' }}>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{signal.symbol}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{new Date(signal.signal_time).toLocaleString()}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{signal.entry.toFixed(5)}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{signal.stop_loss.toFixed(5)}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px' }}>{signal.take_profit.toFixed(5)}</td>
              <td style={{ border: '1px solid #ddd', padding: '8px', color: signal.d_exp.startsWith('+') ? 'blue' : 'red' }}>
                {signal.d_exp}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default SignalsTable;