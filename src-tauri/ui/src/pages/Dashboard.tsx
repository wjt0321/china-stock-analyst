import { useEffect, useState } from "react";
import { getWatchlist, analyzeStock } from "../api/sidecar";

export default function Dashboard() {
  const [watchlist, setWatchlist] = useState<any[]>([]);

  useEffect(() => {
    getWatchlist().then((res: any) => setWatchlist(res.data || []));
  }, []);

  return (
    <div>
      <h1>自选股看板</h1>
      <ul>
        {watchlist.map((item) => (
          <li key={item.stock_code}>
            {item.stock_code} {item.stock_name}
            <button onClick={() => analyzeStock([item.stock_code])}>分析</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
