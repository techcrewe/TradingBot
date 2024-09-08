import React, { useEffect, useRef, useState } from 'react';
import { createChart } from 'lightweight-charts';
import axios from 'axios';

const LightweightChart = ({ symbol, chartSymbol }) => {
  const chartContainerRef = useRef();
  const chartRef = useRef();
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchOHLCData = async () => {
      try {
        console.log(`Fetching OHLC data for symbol: ${symbol}`);
        const response = await axios.get(`http://localhost:8000/api/ohlc/${chartSymbol}`, {
          withCredentials: false
        });
        console.log('OHLC data received:', response.data.length, 'data points');
        
        if (!chartRef.current) {
          chartRef.current = createChart(chartContainerRef.current, {
            width: 600,
            height: 300,
            layout: {
              background: { type: 'solid', color: '#000000' },
              textColor: '#d1d4dc',
            },
            grid: {
              vertLines: { color: '#404040' },
              horzLines: { color: '#404040' },
            },
            crosshair: {
              mode: 0,  // This sets the crosshair to move freely
            },
            timeScale: {
              timeVisible: true,
              secondsVisible: false,
            },
          });
        }

        const chart = chartRef.current;

        const candleSeries = chart.addCandlestickSeries({
          upColor: '#26a69a',
          downColor: '#ef5350',
          borderVisible: false,
          wickUpColor: '#26a69a',
          wickDownColor: '#ef5350',
        });
        
        const formattedData = response.data.map(d => ({
          time: d.time,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close
        }));
        
        candleSeries.setData(formattedData);

        // Add 20-day Moving Average
        const sma20 = chart.addLineSeries({
          color: 'rgba(255, 255, 255, 0.5)',
          lineWidth: 2,
        });
        const sma20Data = calculateSMA(formattedData, 20);
        sma20.setData(sma20Data);

        // Add 50-day Moving Average
        const sma50 = chart.addLineSeries({
          color: 'rgba(255, 0, 0, 0.5)',
          lineWidth: 2,
        });
        const sma50Data = calculateSMA(formattedData, 50);
        sma50.setData(sma50Data);

        chart.timeScale().fitContent();

        setError(null);
      } catch (error) {
        console.error('Error fetching OHLC data:', error.response ? error.response.data : error.message);
        setError('Failed to fetch OHLC data');
      }
    };

    fetchOHLCData();

    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [symbol, chartSymbol]);

  const calculateSMA = (data, period) => {
    const sma = [];
    for (let i = period - 1; i < data.length; i++) {
      const sum = data.slice(i - period + 1, i + 1).reduce((total, candle) => total + candle.close, 0);
      sma.push({ time: data[i].time, value: sum / period });
    }
    return sma;
  };

  if (error) {
    return <div style={{ color: 'red' }}>{error}</div>;
  }

  return (
    <div>
      <h2 style={{ color: '#d1d4dc' }}>Chart for {chartSymbol}</h2>
      <div ref={chartContainerRef} />
    </div>
  );
};

export default LightweightChart;