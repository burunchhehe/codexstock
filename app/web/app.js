const symbols = ["083450", "005930", "000660", "NVDA", "AAPL", "MSFT", "TSM", "AVGO"];
const researchUniverse = [
  { symbol: "083450", name: "GST", market: "KR-KOSDAQ", choseong: "GST" },
  { symbol: "005930", name: "\uc0bc\uc131\uc804\uc790", market: "KR", choseong: "\u3145\u3145\u3148\u3148" },
  { symbol: "000660", name: "SK\ud558\uc774\ub2c9\uc2a4", market: "KR", choseong: "SK\u314e\u3147\u3134\u3145" },
  { symbol: "005380", name: "\ud604\ub300\ucc28", market: "KR", choseong: "\u314e\u3137\u314a" },
  { symbol: "035420", name: "NAVER", market: "KR", choseong: "NAVER" },
  { symbol: "051910", name: "LG\ud654\ud559", market: "KR", choseong: "LG\u314e\u314e" },
  { symbol: "006400", name: "\uc0bc\uc131SDI", market: "KR", choseong: "\u3145\u3145SDI" },
  { symbol: "AAPL", name: "Apple", market: "US", choseong: "AAPL" },
  { symbol: "MSFT", name: "Microsoft", market: "US", choseong: "MSFT" },
  { symbol: "NVDA", name: "NVIDIA", market: "US", choseong: "NVDA" },
  { symbol: "TSLA", name: "Tesla", market: "US", choseong: "TSLA" },
  { symbol: "AMZN", name: "Amazon", market: "US", choseong: "AMZN" },
  { symbol: "META", name: "Meta", market: "US", choseong: "META" },
  { symbol: "GOOGL", name: "Alphabet", market: "US", choseong: "GOOGL" },
  { symbol: "AMD", name: "AMD", market: "US", choseong: "AMD" },
  { symbol: "SPY", name: "S&P500 ETF", market: "US", choseong: "SPY" },
  { symbol: "QQQ", name: "Nasdaq100 ETF", market: "US", choseong: "QQQ" },
];
researchUniverse.push(
  ...[
    ["000270", "\uae30\uc544", "KR", "\u3131\u3147"], ["068270", "\uc140\ud2b8\ub9ac\uc628", "KR", "\u3145\u314c\u3139\u3147"], ["207940", "\uc0bc\uc131\ubc14\uc774\uc624\ub85c\uc9c1\uc2a4", "KR", "\u3145\u3145\u3142\u3147\u3147"], ["005490", "POSCO\ud640\ub529\uc2a4", "KR", "POSCO"], ["373220", "LG\uc5d0\ub108\uc9c0\uc194\ub8e8\uc158", "KR", "LG\u3147\u3134\u3148"], ["105560", "KB\uae08\uc735", "KR", "KB\u3131\u3147"], ["055550", "\uc2e0\ud55c\uc9c0\uc8fc", "KR", "\u3145\u314e\u3148\u3148"], ["035720", "\uce74\uce74\uc624", "KR", "\u314b\u314b\u3147"], ["012330", "\ud604\ub300\ubaa8\ube44\uc2a4", "KR", "\u314e\u3137\u3141\u3142\u3145"], ["028260", "\uc0bc\uc131\ubb3c\uc0b0", "KR", "\u3145\u3145\u3141\u3145"],
    ["066570", "LG\uc804\uc790", "KR", "LG\u3148\u3148"], ["096770", "SK\uc774\ub178\ubca0\uc774\uc158", "KR", "SK\u3147\u3134"], ["032830", "\uc0bc\uc131\uc0dd\uba85", "KR", "\u3145\u3145\u3145\u3141"], ["086790", "\ud558\ub098\uae08\uc735\uc9c0\uc8fc", "KR", "\u314e\u3134\u3131\u3147"], ["033780", "KT&G", "KR", "KTG"], ["017670", "SK\ud154\ub808\ucf64", "KR", "SK\u314c\u3139\u314b"], ["003550", "LG", "KR", "LG"], ["034020", "\ub450\uc0b0\uc5d0\ub108\ube4c\ub9ac\ud2f0", "KR", "\u3137\u3145\u3147\u3134"], ["009150", "\uc0bc\uc131\uc804\uae30", "KR", "\u3145\u3145\u3148\u3131"], ["010130", "\uace0\ub824\uc544\uc5f0", "KR", "\u3131\u3139\u3147\u3147"],
    ["018260", "\uc0bc\uc131\uc5d0\uc2a4\ub514\uc5d0\uc2a4", "KR", "\u3145\u3145SDS"], ["011200", "HMM", "KR", "HMM"], ["090430", "\uc544\ubaa8\ub808\ud37c\uc2dc\ud53d", "KR", "\u3147\u3141\u3139"], ["251270", "\ub137\ub9c8\ube14", "KR", "\u3134\u3141\u3142"], ["036570", "\uc5d4\uc528\uc18c\ud504\ud2b8", "KR", "\u3147\u3146\u3145\u314d\u314c"], ["011170", "\ub86f\ub370\ucf00\ubbf8\uce7c", "KR", "\u3139\u3137\u314b"], ["010950", "S-Oil", "KR", "SOIL"], ["024110", "\uae30\uc5c5\uc740\ud589", "KR", "\u3131\u3147\u3147\u314e"], ["316140", "\uc6b0\ub9ac\uae08\uc735\uc9c0\uc8fc", "KR", "\u3147\u3139\u3131\u3147"], ["086520", "\uc5d0\ucf54\ud504\ub85c", "KR", "\u3147\u314b\u314d\u3139"],
    ["BRK.B", "Berkshire Hathaway", "US", "BRKB"], ["JPM", "JPMorgan", "US", "JPM"], ["V", "Visa", "US", "V"], ["MA", "Mastercard", "US", "MA"], ["UNH", "UnitedHealth", "US", "UNH"], ["LLY", "Eli Lilly", "US", "LLY"], ["AVGO", "Broadcom", "US", "AVGO"], ["COST", "Costco", "US", "COST"], ["WMT", "Walmart", "US", "WMT"], ["HD", "Home Depot", "US", "HD"],
    ["PG", "Procter & Gamble", "US", "PG"], ["KO", "Coca-Cola", "US", "KO"], ["PEP", "PepsiCo", "US", "PEP"], ["MCD", "McDonald's", "US", "MCD"], ["XOM", "Exxon Mobil", "US", "XOM"], ["CVX", "Chevron", "US", "CVX"], ["ORCL", "Oracle", "US", "ORCL"], ["CRM", "Salesforce", "US", "CRM"], ["ADBE", "Adobe", "US", "ADBE"], ["NFLX", "Netflix", "US", "NFLX"],
    ["INTC", "Intel", "US", "INTC"], ["QCOM", "Qualcomm", "US", "QCOM"], ["TXN", "Texas Instruments", "US", "TXN"], ["BA", "Boeing", "US", "BA"], ["CAT", "Caterpillar", "US", "CAT"], ["GE", "GE Aerospace", "US", "GE"], ["NKE", "Nike", "US", "NKE"], ["DIS", "Disney", "US", "DIS"], ["PYPL", "PayPal", "US", "PYPL"], ["COIN", "Coinbase", "US", "COIN"]
  ].map(([symbol, name, market, choseong]) => ({ symbol, name, market, choseong }))
);

const strategyPresets = [
  { id: "ma-default", name: "\uae30\uc900 MA 12/32", owner: "\uc6b0\ub9ac \uae30\uc900\uc804\ub7b5", fast: 12, slow: 32, memo: "\ub2e8\uae30 \uc774\ud3c9\uc120\uc774 \uc7a5\uae30 \uc774\ud3c9\uc120\uc744 \uc0c1\ud5a5\ud560 \ub54c \ub9e4\uc218" },
  { id: "buffett-quality", name: "\uc6cc\ub80c \ubc84\ud54f\ud615 \ud488\uc9c8/\uc7a5\uae30", owner: "Warren Buffett", fast: 50, slow: 200, memo: "\uc7a5\uae30 \ucd94\uc138\uc640 \ub0ae\uc740 \ud68c\uc804\uc728\uc744 \uc911\uc2dc\ud558\ub294 \ubcf4\uc218\uc801 \ub300\uccb4 \ud504\ub9ac\uc14b" },
  { id: "minervini-momentum", name: "\ub9c8\ud06c \ubbf8\ub108\ube44\ub2c8\ud615 \ubaa8\uba58\ud140", owner: "Mark Minervini", fast: 10, slow: 30, memo: "\uac15\ud55c \ucd94\uc138\uc758 \ucd08\uae30 \uad6c\uac04\uc744 \ube60\ub974\uac8c \uc7a1\ub294 \ubaa8\uba58\ud140 \ud504\ub9ac\uc14b" },
  { id: "turtle-trend", name: "\ud130\ud2c0 \ud2b8\ub808\uc774\ub354 \ucd94\uc138\ucd94\uc885", owner: "Turtle Traders", fast: 20, slow: 55, memo: "\ub3cc\ud30c/\ucd94\uc138 \uc9c0\uc18d\uc131\uc744 \uac00\uc815\ud55c \ud504\ub9ac\uc14b" },
  { id: "o-neil-canslim", name: "\uc70c\ub9ac\uc5c4 \uc624\ub2d0 CANSLIM\ud615", owner: "William O'Neil", fast: 21, slow: 50, memo: "\uc131\uc7a5\uc8fc \ucd94\uc138\uc640 \uc0c1\ub300\uac15\ub3c4\ub97c \uac00\uc815\ud55c \ud504\ub9ac\uc14b" },
  { id: "graham-defensive", name: "\ubca4\uc800\ubbfc \uadf8\ub808\uc774\uc5c4 \ubc29\uc5b4\ud615", owner: "Benjamin Graham", fast: 60, slow: 180, memo: "\uc190\uc2e4\ud68c\ud53c\uc640 \uc7a5\uae30 \uac00\uce58 \ud68c\uadc0\ub97c \uc911\uc2dc\ud558\ub294 \ud504\ub9ac\uc14b" },
  { id: "lynch-growth", name: "\ud53c\ud130 \ub9b0\uce58 \uc131\uc7a5\uac00\uce58\ud615", owner: "Peter Lynch", fast: 30, slow: 90, memo: "\uc131\uc7a5\uc131\uacfc \ucd94\uc138 \uc9c0\uc18d\uc744 \uc911\uac04 \ud638\ud761\uc73c\ub85c \ud655\uc778" },
];
if (window.location.protocol === "file:") {
  window.location.replace("http://127.0.0.1:8765/");
  throw new Error("Run the app through the local HTS server.");
}

const t = {
  appTitle: "코덱스스톡",
  dashboard: "\ub300\uc2dc\ubcf4\ub4dc",
  trading: "AI 감독/승인",
  research: "\uc804\ub7b5 \uc5f0\uad6c",
  aiTrader: "AI \ud2b8\ub808\uc774\ub354",
  settings: "\uc124\uc815",
  logic: "\ub85c\uc9c1 \uad00\ub9ac",
  journal: "\ubcf5\uae30/\ub9ac\uc2a4\ud06c",
  normal: "\uc815\uc0c1",
  partial: "\ubd80\ubd84",
  symbol: "\uc885\ubaa9",
  price: "\ud604\uc7ac\uac00",
  change: "\ub4f1\ub77d\ub960",
  selected: "\uc120\ud0dd \uc885\ubaa9",
  watch: "\uad00\uc2ec\uc885\ubaa9",
  orderbook: "\ud638\uac00\ucc3d",
  spread: "\uc2a4\ud504\ub808\ub4dc",
  buy: "\ub9e4\uc218",
  sell: "\ub9e4\ub3c4",
  auto: "\uc790\ub3d9",
  quantity: "\uc218\ub7c9",
  paper: "AI 훈련 장부",
  cash: "\ud604\uae08",
  marketValue: "\ud3c9\uac00\uae08",
  noPosition: "\ubcf4\uc720 \uc5c6\uc74c",
  priceLegend: "\uac00\uaca9",
  equityLegend: "\ud3c9\uac00\uace1\uc120",
  maLegend: "\uc774\ub3d9\ud3c9\uade0",
  dashboardLabel: "\uc624\ub298\uc758 \uc790\ub3d9\ub9e4\ub9e4 \uc0c1\ud0dc",
  dashboardTitle: "코덱스스톡 작전실",
  dashboardSub: "\uc2dc\uc7a5 \uc0c1\ud0dc, \uc804\ub7b5 \uac80\uc99d, \ub9ac\uc2a4\ud06c \ud55c\ub3c4, \ubcf5\uae30\ub97c \ud55c \ud654\uba74\uc5d0\uc11c \ud655\uc778\ud569\ub2c8\ub2e4.",
  openTrading: "AI 후보 감독",
  openResearch: "\uc804\ub7b5 \uc5f0\uad6c \uc2e4\ud589",
  openLogic: "100억 프로젝트",
  autoPilot: "\uc790\ub3d9 \uac10\uc2dc",
  decisionReady: "\uc2dc\uc7a5 \ub370\uc774\ud130\ub97c \uac31\uc2e0\ud558\uba70 \ub2e8\uae30/\uc7a5\uae30\uc120 \uc870\uac74\uc744 \uac80\uc0ac \uc911\uc785\ub2c8\ub2e4.",
  equityHint: "\ubaa8\uc758\uacc4\uc88c \uae30\uc900",
  returnHint: "\ucd5c\uadfc \ubc31\ud14c\uc2a4\ud2b8",
  riskHint: "\uc77c\uc77c \uc8fc\ubb38 \uc0ac\uc6a9\ub960",
  logicHint: "전략 연구/훈련 기록",
  marketBreadth: "\uc0c1\uc2b9 {up} / \ud558\ub77d {down}",
  topMover: "\uac15\uc138 \uc885\ubaa9",
  weakMover: "\uc57d\uc138 \uc885\ubaa9",
  volLeader: "\uac70\ub798 \uc8fc\ub3c4",
  missionTitle: "\uc624\ub298\uc758 \uc791\uc804 \ud750\ub984",
  missionBadge: "전략 검증+자동운용",
  missionScan: "\uc2dc\uc7a5 \uc2a4\uce94",
  missionScanSub: "\uad00\uc2ec\uc885\ubaa9 \ubcc0\ub3d9\ub960\uacfc \uac70\ub798\ub7c9\uc744 \uc0c1\uc2dc \uac10\uc2dc",
  missionTest: "\uc804\ub7b5 \uac80\uc99d",
  missionTestSub: "\ubc31\ud14c\uc2a4\ud2b8\uc640 \ud6c4\ubcf4 \uc804\ub7b5 \uc21c\uc704\ud654",
  missionRisk: "\ub9ac\uc2a4\ud06c \ucc28\ub2e8",
  missionRiskSub: "\uc8fc\ubb38 \ud69f\uc218\uc640 \uc885\ubaa9 \ube44\uc911 \ud55c\ub3c4 \uac80\uc0ac",
  missionReview: "\ubcf5\uae30 \uae30\ub85d",
  missionReviewSub: "\uc8fc\ubb38, \uc5f0\uad6c, \ub85c\uc9c1 \ubcc0\uacbd\uc744 \uc790\ub3d9 \uae30\ub85d",
  riskConsole: "\ub9ac\uc2a4\ud06c \ucf58\uc194",
  riskSafe: "\uc548\uc804",
  riskCaution: "\uc8fc\uc758",
  orderUsage: "\uc8fc\ubb38 \uc0ac\uc6a9",
  positionCap: "\uc885\ubaa9 \ud55c\ub3c4",
  equity: "\ucd1d \ud3c9\uac00",
  returnRate: "\uc218\uc775\ub960",
  risk: "\ub9ac\uc2a4\ud06c",
  logicCount: "전략 기록",
  candidates: "\uc804\ub7b5 \ud6c4\ubcf4",
  recentLog: "\ucd5c\uadfc \ubcf5\uae30",
  strategyLab: "\uc804\ub7b5 \uc2e4\ud5d8\uc2e4",
  runResearch: "\uc804\ub7b5 \uc5f0\uad6c",
  runBacktest: "\ubc31\ud14c\uc2a4\ud2b8",
  runMultiBacktest: "\ub2e4\uc911\ube44\uad50",
  days: "\uae30\uac04",
  startDate: "\uc2dc\uc791\uc77c",
  endDate: "\uc885\ub8cc\uc77c",
  symbolSearch: "\uc885\ubaa9 \uac80\uc0c9",
  strategyPresetLabel: "\uc720\uba85 \uc804\ub7b5/\ud22c\uc790\uc790",
  strategyChart: "\uc804\ub7b5 \uacb0\uacfc \ucc28\ud2b8",
  multiCompare: "\uc885\ubaa9\ubcc4 10\ub144 \uc804\ub7b5 \ube44\uad50",
  transcriptStrategy: "\uc790\ub9c9/\uc720\ud29c\ube0c \uc804\ub7b5 \ubc31\ud14c\uc2a4\ud2b8",
  runTranscriptStrategy: "\uc790\ub9c9\uc804\ub7b5 \uc2e4\ud589",
  fast: "\ub2e8\uae30\uc120",
  slow: "\uc7a5\uae30\uc120",
  finalEquity: "\ucd5c\uc885 \ud3c9\uac00\uae08",
  totalReturn: "\ucd1d\uc218\uc775\ub960",
  maxDrawdown: "\ucd5c\ub300\ub099\ud3ed",
  trades: "\ub9e4\ub9e4\ud69f\uc218",
  candidateList: "\ud6c4\ubcf4 \uc21c\uc704",
  waiting: "\ub300\uae30",
  running: "\uc2e4\ud589 \uc911",
  done: "\uc644\ub8cc",
  logicManage: "\ub85c\uc9c1 \uc800\uc7a5/\uba54\ubaa8",
  saveLogic: "\ub85c\uc9c1 \uc800\uc7a5",
  compareLogic: "\ub85c\uc9c1 \ube44\uad50",
  compareResult: "\ube44\uad50 \uacb0\uacfc",
  eventLog: "\uc774\ubca4\ud2b8 \ub85c\uadf8",
  clear: "\uc9c0\uc6b0\uae30",
  riskStatus: "\ub9ac\uc2a4\ud06c \uc0c1\ud0dc",
  orderLimit: "\uc8fc\ubb38 \ud55c\ub3c4",
  positionLimit: "\uc885\ubaa9 \ud55c\ub3c4",
  sourceCount: "분석 엔진",
  waitSignal: "\uc2e0\ud638 \uc5c6\uc74c",
  hold: "\ubcf4\uc720",
  filled: "\uccb4\uacb0",
  learnTitle: "전략 검증 작업 흐름",
  learnSub: "단순 HTS가 아니라 로직을 저장하고, 비교하고, 복기하는 자체 전략 관리 흐름",
  learnLogic: "\ub85c\uc9c1 \uc800\uc7a5",
  learnLock: "\uc7a0\uae08/\uba54\ubaa8",
  learnCompare: "\uae30\uc900 \ub300\ube44 \ube44\uad50",
  learnHistory: "\ud788\uc2a4\ud1a0\ub9ac/\ubcf5\uae30",
  learnRisk: "\ub9ac\uc2a4\ud06c \uac00\ub4dc",
  logicLearnTitle: "자체 전략 관리 흐름",
  logicLearnSub: "저장, 메모, 잠금, 비교를 코덱스스톡 전략 관리로 정리했습니다",
  logicMapSave: "\ucd94\ucc9c\ub85c\uc9c1 \uc800\uc7a5",
  logicMapCompare: "\ub85c\uc9c1 \ube44\uad50",
  logicMapMemo: "\uba54\ubaa8/\uc7a0\uae08",
  apiStatus: "API \uc5f0\ub3d9",
  apiReady: "\uc5f0\uacb0\uc900\ube44",
  apiMissing: "\ubbf8\uc124\uc815",
  apiLocked: "\uc2e4\uc804\uc8fc\ubb38 \uc7a0\uae08",
  kis: "\ud55c\uad6d\ud22c\uc790",
  kisMode: "KIS \ubaa8\ub4dc",
  dart: "DART \uacf5\uc2dc",
  toss: "토스 공개",
  ecos: "한국은행 ECOS",
  fred: "FRED 거시",
  liveTrading: "\uc2e4\uc804\ub9e4\ub9e4",
  apiNote: "\ud0a4\ub294 .env\uc5d0\uc11c\ub9cc \uc77d\uace0 \ud654\uba74\uc5d0\ub294 \ub178\ucd9c\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
  refreshApi: "API \uc0c8\ub85c\uace0\uce68",
  dartEmpty: "\uc870\ud68c\ub41c \uacf5\uc2dc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.",
  disabled: "\ucc28\ub2e8",
  enabled: "\ucf1c\uc9d0",
  macroLiveTitle: "ECOS/FRED 거시지표",
  macroMissing: "ECOS 또는 FRED 키가 없거나 아직 조회된 지표가 없습니다.",
  kisAccountTitle: "한투 실제 계좌",
  kisLiveTitle: "\ud55c\ud22c \uc2e4\uc2dc\uac04 \uc2dc\uc138",
  dartLiveTitle: "DART \uc2e4\uc81c \uacf5\uc2dc",
  sourceKis: "KIS \uc77d\uae30\uc804\uc6a9",
  dataFail: "\ub370\uc774\ud130 \uc870\ud68c \uc2e4\ud328",
  liveResearch: "\uc2e4\ub370\uc774\ud130 \uc885\ubaa9 \ub9ac\uc11c\uce58",
  runLiveResearch: "\uc2e4\ub370\uc774\ud130 \uc2a4\uce94",
  actionWatch: "\uad00\uc2ec",
  actionCaution: "\uc8fc\uc758",
  actionWait: "\ub300\uae30",
  aiTraderLabel: "24\uc2dc\uac04 \uace0\uc6a9\ud615 AI",
  aiTraderTitle: "\ub0b4 \ub300\uc2e0 \uac10\uc2dc\ud558\ub294 AI \ud2b8\ub808\uc774\ub354 \ub370\uc2a4\ud06c",
  refreshAiBrief: "\ube0c\ub9ac\ud551 \uac31\uc2e0",
  sendTelegramBrief: "\ud154\ub808\uadf8\ub7a8 \ubcf4\uace0",
  aiKrTitle: "\uad6d\ub0b4\uc2dc\uc7a5",
  aiUsTitle: "\ubbf8\uad6d\uc2dc\uc7a5",
  telegramTitle: "\ud154\ub808\uadf8\ub7a8 \uc790\ub3d9\ubcf4\uace0",
  economicSignalTitle: "경제지표 신호",
  hedgeStrategyTitle: "\ud5f7\uc9d5 \uc804\ub7b5 \ube44\uad50",
  telegramSent: "\ubcf4\uace0 \uc694\uccad \uc644\ub8cc",
};

const pageGuide = {
  dashboard: { title: "대시보드", tab: "전체 현황", desc: "계좌, 시장, API, 위험, 후보를 한눈에 보는 첫 화면" },
  aiTrader: { title: "AI 트레이더", tab: "AI 직원", desc: "AI 연구원·운용직원·오토파일럿·텔레그램 시간표 보고 관리" },
  recommendations: { title: "추천 종목", tab: "섹터 리서치", desc: "섹터별 AI 추천, 후보 점수, 기업 심층 리포트, 뉴스·재무 레이더" },
  trading: { title: "AI 감독/승인", tab: "감독석", desc: "AI가 24시간 만든 후보와 훈련 매매를 사람이 확인·승인·거절·중단" },
  research: { title: "전략 연구", tab: "실험실+저장", desc: "백테스트, 과거장 훈련, 전략 저장/비교를 한곳에서 관리" },
  capitalChallenge: { title: "100억 프로젝트", tab: "장기 성장", desc: "1천만원으로 과거 차트 100억 목표를 향해 전략을 계속 훈련" },
  settings: { title: "설정/기록", tab: "환경+리스크", desc: "AI 모델, API, 리스크 기록, 친구 배포 준비 관리" },
  logic: { title: "전략 저장/비교", tab: "전략 연구에 통합", desc: "전략 연구 안으로 합쳐진 고급 기능" },
  journal: { title: "운영 기록", tab: "설정에 통합", desc: "설정/기록 안으로 합쳐진 고급 기능" },
};

const state = {
  active: "083450",
  quotes: new Map(),
  history: new Map(),
  historyDates: new Map(),
  historySource: new Map(),
  minuteRows: new Map(),
  minuteSource: new Map(),
  minuteMomentum: new Map(),
  intradayMinuteRadar: null,
  conditionScreenerTimer: null,
  lastConditionScreener: null,
  lastConditionScreenerHistory: null,
  lastLiveDecisionContext: null,
  aiStaffMeetingSplitLoadedAt: 0,
  equity: [],
  orderbook: null,
  marketBusy: false,
  positionSignature: "",
  lastPortfolio: null,
  lastCandidates: [],
  lastLogs: [],
  integrations: null,
  macroSnapshot: null,
  selectedResearchSymbols: ["083450", "005930", "000660"],
  replaySelectedSymbols: ["083450", "005930", "NVDA"],
  lastMultiBacktest: null,
  lastValidationResult: null,
  lastValidationParams: null,
  lastOpsStatus: null,
  hotLogStorage: null,
  hotLogStorageLoadedAt: 0,
  hotLogStorageLoading: false,
  lastLivePilotPlan: null,
  livePilotPlanLoadedAt: 0,
  livePilotPlanLoading: false,
  lastLivePilotSide: "BUY",
  lastLiveCandidateDecision: null,
  liveCandidateDecisionLoadedAt: 0,
  liveCandidateDecisionLoading: false,
  lastDaytradeStudy: null,
  lastTradeJournalSummary: null,
  lastScreenerResult: null,
  lastCapitalChallenge: null,
  lastCapitalPhaseTraining: null,
  activeCapitalPhaseTraining: "",
  capitalActionHistory: [],
  lastHundredLabStatus: null,
  hideHundredLabHighRisk: false,
  sortHundredLabByEfficiency: false,
  lastAiTournament: null,
  aiTournamentRunning: false,
  aiTournamentChampions: [],
  capitalScenarioCatalog: [],
  capitalChallengeJobTimer: null,
  competitiveAuditBusy: false,
  competitiveAuditJobRunning: false,
  competitiveAuditJobTimer: null,
  lastMaturityScore: null,
  lastApprovalToken: "",
  accountView: "paper",
  liveAccountSnapshot: null,
  livePerformance: null,
  livePerformanceDateFilter: "",
  livePerformancePage: 1,
  livePerformancePageSize: 4,
  latestBrokerJournal: null,
  liveExitPlans: new Map(),
  liveExitPlanLoading: new Set(),
  liveExitPlanFetchedAt: new Map(),
  todayBrokerExecutions: null,
  todayBrokerExecutionsFetchedAt: 0,
  liveAccountChanges: null,
  universeStats: { count: researchUniverse.length, source: "내장" },
  watchlist: [],
  watchlistSearchIndex: -1,
  recommendations: [],
  recommendationPageHydrated: false,
  sectorNews: null,
  priceChart: {
    symbol: "",
    start: 0,
    end: null,
    total: 0,
    dragging: false,
    dragStartX: 0,
    dragStartStart: 0,
    dragStartEnd: 0,
    hoverX: null,
  },
  strategyChart: {
    results: [],
    start: 0,
    end: null,
    dragging: false,
    dragStartX: 0,
    dragStartStart: 0,
    dragStartEnd: 0,
    hoverX: null,
  },
};

const el = (selector) => document.querySelector(selector);
const APP_NAME_STORAGE_KEY = "codexStock.customAppName";
const TAB_ORDER_STORAGE_KEY = "codexStock.tabOrder";
const HUNDRED_LAB_HIDE_RISK_STORAGE_KEY = "codexStock.hundredLab.hideHighRisk";
const HUNDRED_LAB_EFFICIENCY_SORT_STORAGE_KEY = "codexStock.hundredLab.efficiencySort";
const CAPITAL_ACTION_HISTORY_STORAGE_KEY = "codexStock.capitalActionHistory";
function savedHundredLabHideRisk() {
  try {
    return localStorage.getItem(HUNDRED_LAB_HIDE_RISK_STORAGE_KEY) === "1";
  } catch (_) {
    return false;
  }
}
function savedHundredLabEfficiencySort() {
  try {
    return localStorage.getItem(HUNDRED_LAB_EFFICIENCY_SORT_STORAGE_KEY) === "1";
  } catch (_) {
    return false;
  }
}
function savedCapitalActionHistory() {
  try {
    const rows = JSON.parse(localStorage.getItem(CAPITAL_ACTION_HISTORY_STORAGE_KEY) || "[]");
    if (!Array.isArray(rows)) return [];
    const allowed = new Set(["start", "running", "success", "error", "info"]);
    return rows
      .map((row) => ({
        status: allowed.has(row?.status) ? row.status : "info",
        title: String(row?.title || "작업 기록").slice(0, 80),
        detail: String(row?.detail || "-").slice(0, 240),
        time: String(row?.time || "").slice(0, 30),
      }))
      .slice(0, 7);
  } catch (_) {
    return [];
  }
}
state.hideHundredLabHighRisk = savedHundredLabHideRisk();
state.sortHundredLabByEfficiency = savedHundredLabEfficiencySort();
state.capitalActionHistory = savedCapitalActionHistory();
const money = (value) => Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money0 = (value) => Number(value || 0).toLocaleString("ko-KR", { maximumFractionDigits: 0 });
const pct = (value) => `${value >= 0 ? "+" : ""}${Number(value).toFixed(2)}%`;
const signedMoney = (value) => `${Number(value || 0) >= 0 ? "+" : "-"}${money(Math.abs(Number(value || 0)))}`;
const shortDateLabel = (value) => {
  const text = String(value || "");
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[2]}/${match[3]}` : text.slice(0, 10) || "-";
};
const dataSourceLabel = (payload = {}) => {
  const mode = payload.data_mode === "real" ? "실데이터" : payload.data_mode === "mixed" ? "혼합데이터" : payload.data_mode === "simulated" ? "샘플데이터" : "데이터";
  const source = payload.data_source || payload.data_provider || payload.source || "";
  return source ? `${mode} · ${source}` : mode;
};
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  "\"": "&quot;",
  "'": "&#39;",
}[char]));

function productText(value) {
  return String(value ?? "")
    .replace(/HepiStock|hepi[-_ ]?stock|Hepi[A-Za-z0-9_. /-]*|헤피[^\s,.)]*/gi, "운영 엔진")
    .replace(/QuantKing|quantking|퀀트킹/gi, "전략 검증")
    .replace(/Freqtrade|QuantConnect\s*LEAN|LEAN|vectorbt|Backtrader|vn\.py|FinRL-X|Zipline/gi, "고급 자동매매 구조")
    .replace(/GitHub|github|깃허브|오픈소스|open source/gi, "확장 구조")
    .replace(/최강\s*소스|최강소스/g, "기능 완성도")
    .replace(/참고\s*소스/g, "분석 엔진")
    .replace(/흡수|이식/g, "구현")
    .replace(/가져온/g, "반영한")
    .replace(/참고한/g, "검토한");
}

const productHtml = (value) => escapeHtml(productText(value));

const BUTTON_HELP = {
  refreshAiBrief: "AI 시장 브리핑을 새로 불러옵니다. 실제 주문은 실행하지 않습니다.",
  sendTelegramBrief: "현재 브리핑을 텔레그램 발송 큐에 넣습니다.",
  refreshPreMarketBrief: "장전 뉴스와 시장 이슈 브리핑을 다시 생성합니다.",
  queuePreMarketBrief: "장전 브리핑을 텔레그램 보고 큐에 넣습니다.",
  analyzeKrMarket: "한국장 흐름, 수급, 주도 섹터 요약을 다시 분석합니다.",
  runMissionCycle: "AI 연구 사이클을 1회 실행해 기록과 후보를 갱신합니다.",
  runAutopilotTick: "자동 운용 루프를 한 번만 점검 실행합니다. 실주문은 별도 승인 없이는 전송하지 않습니다.",
  startAutopilotScheduler: "정해진 주기로 자동 점검 루프를 켭니다.",
  stopAutopilotScheduler: "자동 점검 루프를 멈춥니다.",
  runScreener: "시장 후보를 다시 훑어 추천 종목 풀을 갱신합니다.",
  runSectorCommittee: "후보 종목보다 먼저 업종 순위, 목표 비중, 편중 경고를 회의 형식으로 계산합니다.",
  refreshRecommendations: "추천 종목 화면을 새 데이터로 갱신합니다.",
  refreshOpportunities: "섹터별 추천 카드와 상승 여력 설명을 다시 계산합니다.",
  runRadar: "뉴스, 재무, 이슈 레이더를 새로 수집합니다.",
  runSectorNews: "섹터별 뉴스 요약을 수집하고 기록합니다.",
  runDossier: "선택한 종목의 재무, 뉴스, 리스크, 투자 포인트를 심층 분석합니다.",
  runBacktest: "현재 선택한 전략과 기간으로 백테스트를 실행합니다.",
  runMultiBacktest: "여러 종목을 같은 전략으로 비교합니다.",
  runRobustness: "전략이 기간과 파라미터 변화에도 버티는지 검증합니다.",
  runProtections: "손절, 쿨다운, 최대낙폭 같은 보호장치를 비교합니다.",
  runHistoricalReplay: "과거 장을 리플레이하며 모의 훈련을 실행합니다.",
  runValidationSuite: "전략 후보를 승률, MDD, 거래횟수 기준으로 검증합니다.",
  runTranscriptStrategy: "자막이나 메모에서 전략 규칙을 뽑아 백테스트합니다.",
  refreshCapitalChallenge: "저장된 최신 100억 프로젝트 결과를 불러옵니다.",
  runCapitalChallenge: "2000년부터 현재까지 100억 프로젝트 전체 훈련을 새로 실행합니다.",
  refreshHundredLab: "전략 후보 탐색기의 최근 상태를 불러옵니다.",
  copyHundredLabTop: "전략 후보 탐색기에서 현재 화면에 표시된 상위 후보 요약을 클립보드에 복사합니다.",
  downloadHundredLabTop: "전략 후보 탐색기에서 현재 화면에 표시된 상위 후보 요약을 Markdown 파일로 저장합니다.",
  toggleHundredLabHideRisk: "낙폭 위험 후보를 화면에서 잠시 숨기거나 다시 표시합니다.",
  toggleHundredLabEfficiencySort: "현재 TOP10 후보를 위험효율이 높은 순서로 잠시 재정렬합니다.",
  stopHundredLab: "진행 중인 전략 후보 탐색을 멈춥니다.",
  runCompetitiveAudit: "현재 기능 완성도를 빠르게 점검하고 다음 개선 버튼을 추천합니다.",
  runCompetitiveAuditFull: "기능 완성도를 정밀 점검합니다. 시간이 더 걸릴 수 있습니다.",
  opsPaperBuy: "선택 종목을 모의투자 계좌에만 기록합니다.",
  opsLiveCandidate: "실전 주문 전송 전 후보 티켓만 만듭니다.",
  opsApproveLatest: "가장 최근 승인 대기 티켓을 허용 상태로 바꿉니다.",
  opsDrySubmit: "실전 전송 전 주문 가능 여부를 모의 검증합니다.",
  opsQueueTelegram: "운영 상태 요약을 텔레그램 보고 큐에 넣습니다.",
  opsSavePolicy: "자동매매 한도, 손실정지, 실전 스위치 설정을 저장합니다.",
  opsAutoStart: "자동 연구와 후보 생성 루프를 켭니다. 실주문은 안전 게이트를 따릅니다.",
  opsAutoStop: "자동 연구와 후보 생성 루프를 멈춥니다.",
  opsEmergencyStop: "모든 자동 운용을 즉시 정지합니다.",
  opsResume: "긴급정지 상태를 해제하고 설정값 기준으로 재개 준비합니다.",
  opsTargetPreview: "AI 후보로 목표 포트폴리오 비중과 주문 가능 수량을 계산합니다.",
  opsApplyPaperTargets: "통과한 목표 포트폴리오를 모의투자에 반영합니다.",
  refreshLiveAccountChanges: "한투 계좌를 읽기전용으로 조회해 수동 매매, 입금, 보유수량 변화를 확인합니다.",
  pilotPlanRefresh: "AI 실전 파일럿 후보를 빠르게 점검합니다.",
  pilotPlanFullRefresh: "호가, 분봉, 체결강도, 주문근거까지 전체 검증합니다. 조회가 조금 더 오래 걸릴 수 있습니다.",
  refreshIntradayMinuteRadar: "관심종목과 AI 후보의 한투 분봉, 체결강도, 매수압력을 읽기전용으로 비교합니다.",
  refreshLiveDecisionContext: "최근 조건검색, 분봉, 체결강도, 호가잔량, 안전게이트를 한 화면 판단으로 묶습니다.",
  refreshLiveDecisionContextDeep: "한투 실데이터 레이더를 다시 조회해서 통합 판단 근거를 더 촘촘히 갱신합니다.",
  pilotCreateCandidate: "AI가 판단한 매수 후보 티켓을 만듭니다.",
  pilotCreateSellCandidate: "AI가 판단한 매도 후보 티켓을 만듭니다.",
  pilotLiveSubmit: "확인 문구와 안전 게이트 통과 후 실주문 전송을 시도합니다.",
  aiTrainingToggle: "연구 AI의 백테스트, 과거장 훈련, 장기기억 기록 루프를 켜거나 끕니다.",
  startAiDaemon: "AI 직원 백그라운드 작업을 시작합니다.",
  runAiCycle: "AI 직원 회의와 연구 작업을 한 번 실행합니다.",
  stopAiDaemon: "AI 직원 백그라운드 작업을 멈춥니다.",
  buyButton: "테스트 매수 버튼입니다. 실전 주문이 아니라 화면 훈련용 주문입니다.",
  sellButton: "테스트 매도 버튼입니다. 실전 주문이 아니라 화면 훈련용 주문입니다.",
  autoButton: "현재 선택 종목으로 AI 전략훈련을 한 번 실행합니다.",
  watchlistAdd: "입력한 종목을 관심종목에 추가합니다.",
  watchlistAddActive: "현재 보고 있는 종목을 관심종목에 추가합니다.",
  watchlistSyncKis: "한투 관심종목과 프로그램 관심종목을 동기화합니다.",
  refreshStatus: "시장, 계좌, 리스크 상태를 새로고침합니다.",
  refreshApiStatus: "API 연결 상태를 다시 확인합니다.",
  clearLog: "화면 하단 이벤트 로그만 비웁니다. 저장 기록은 삭제하지 않습니다.",
  operatorBrainSave: "운용 직원이 사용할 AI 모델 설정을 저장합니다.",
  researcherBrainSave: "연구 직원이 사용할 AI 모델 설정을 저장합니다.",
  copyProgramIntro: "코덱스스톡 소개문을 클립보드에 복사합니다.",
  downloadProgramIntro: "코덱스스톡 소개문을 Markdown 파일로 저장합니다.",
  copyFriendReleaseCommand: "친구 배포 준비도가 통과된 경우에만 패키지 생성 명령을 복사합니다.",
  copyFriendUsageGuide: "친구에게 보낼 첫 사용 안내문을 클립보드에 복사합니다.",
  copyApiSetupGuide: "친구가 본인 API 키를 어디에 넣어야 하는지 안내문을 복사합니다.",
  copyReleaseReadinessSummary: "현재 친구 배포 준비도 점검 결과를 요약해서 복사합니다.",
  downloadReleaseReadinessSummary: "현재 친구 배포 준비도 점검 결과를 Markdown 파일로 저장합니다.",
  copyFriendSharePack: "친구에게 보낼 소개, 사용법, API 안내, 배포 점검 결과 묶음을 클립보드에 복사합니다.",
  downloadFriendSharePack: "친구에게 보낼 소개, 사용법, API 안내, 배포 점검 결과를 하나의 Markdown 파일로 저장합니다.",
  smallAccountRefresh: "소액 계좌 성장 플랜과 현재 작업을 다시 점검합니다.",
  agentPollTelegram: "텔레그램 명령을 즉시 한 번 확인합니다.",
  agentCommandSend: "명령창에 입력한 지시를 AI 트레이더에게 보냅니다.",
};

const PAGE_ACTION_GUIDE = {
  dashboard: {
    headline: "대시보드는 전체 상태 확인용입니다.",
    safety: "여기서 바로 실주문은 나가지 않습니다.",
    actions: [
      { label: "계좌/시장 새로고침", buttonId: "refreshStatus", note: "현재 데이터가 맞는지 먼저 확인합니다." },
      { label: "AI 감독석으로 이동", buttonId: "dashTradeJump", note: "AI 후보와 승인 상태를 확인합니다." },
      { label: "전략 연구로 이동", buttonId: "dashResearchJump", note: "백테스트와 훈련 결과를 봅니다." },
    ],
  },
  aiTrader: {
    headline: "AI 직원이 무엇을 하는지 확인하는 메뉴입니다.",
    safety: "연구와 보고 중심입니다. 실주문은 감독/승인 게이트를 거칩니다.",
    actions: [
      { label: "브리핑 갱신", buttonId: "refreshAiBrief", note: "국내/미국장과 텔레그램 브리핑 내용을 새로 봅니다." },
      { label: "AI 연구 1회 실행", buttonId: "runMissionCycle", note: "후보, 복기, 지식 기록을 한 번 갱신합니다." },
      { label: "AI 백그라운드 시작", buttonId: "startAiDaemon", note: "연구원/운용직원 작업 루프를 켭니다." },
    ],
  },
  recommendations: {
    headline: "추천 종목을 공부하는 리서치 보드입니다.",
    safety: "추천은 후보 설명입니다. 이 메뉴에서 실주문은 전송하지 않습니다.",
    actions: [
      { label: "후보 발굴", buttonId: "runScreener", note: "시장 후보를 다시 추립니다." },
      { label: "추천 카드 갱신", buttonId: "refreshOpportunities", note: "섹터별 카드와 투자 포인트를 다시 계산합니다." },
      { label: "뉴스/재무 레이더", buttonId: "runRadar", note: "뉴스, 재무, 리스크 근거를 확인합니다." },
    ],
  },
  trading: {
    headline: "AI 후보를 사람이 감독하고 승인하는 자리입니다.",
    safety: "실전 주문은 확인 문구와 안전 게이트를 통과해야만 전송됩니다.",
    actions: [
      { label: "AI 후보 빠른 점검", buttonId: "pilotPlanRefresh", note: "현재 실전 파일럿 후보와 차단 사유를 빠르게 확인합니다." },
      { label: "AI 후보 전체 검증", buttonId: "pilotPlanFullRefresh", note: "실제 후보 생성 전 호가, 분봉, 체결강도, 주문근거까지 다시 확인합니다." },
      { label: "실전 후보 생성", buttonId: "opsLiveCandidate", note: "주문 전송이 아니라 승인 대기 티켓만 만듭니다." },
      { label: "긴급정지", buttonId: "opsEmergencyStop", note: "자동 운용이 이상하면 즉시 멈춥니다." },
    ],
  },
  research: {
    headline: "전략을 검증하고 과거장 훈련을 돌리는 실험실입니다.",
    safety: "백테스트와 훈련은 계산/기록용이며 실주문을 보내지 않습니다.",
    actions: [
      { label: "백테스트 실행", buttonId: "runBacktest", note: "선택 종목과 기간으로 전략 성과를 계산합니다." },
      { label: "과거장 훈련", buttonId: "runHistoricalReplay", note: "과거 흐름을 보며 모의 매매 훈련을 기록합니다." },
      { label: "전략 강건성 검증", buttonId: "runRobustness", note: "전략이 구간 변화에도 버티는지 점검합니다." },
    ],
  },
  capitalChallenge: {
    headline: "장기 성장 전략을 반복 훈련하는 프로젝트 메뉴입니다.",
    safety: "100억 프로젝트는 연구/모의 훈련용이며 실전 계좌를 건드리지 않습니다.",
    actions: [
      { label: "최근 결과 보기", buttonId: "refreshCapitalChallenge", note: "저장된 최신 결과와 구간별 성과를 불러옵니다." },
      { label: "전체 프로젝트 실행", buttonId: "runCapitalChallenge", note: "2000년부터 현재까지 전체 훈련을 다시 돌립니다." },
      { label: "실험실 상태 보기", buttonId: "refreshHundredLab", note: "추가 전략 실험의 최근 진행 상태를 확인합니다." },
    ],
  },
  settings: {
    headline: "AI 모델, API, 리스크, 기록을 정비하는 메뉴입니다.",
    safety: "설정 변경은 저장 전까지 적용되지 않으며, API 키는 화면에 노출하지 않습니다.",
    actions: [
      { label: "소개문 복사", buttonId: "copyProgramIntro", note: "GPT나 친구에게 보여줄 코덱스스톡 소개문을 복사합니다." },
      { label: "API 설정 안내 복사", buttonId: "copyApiSetupGuide", note: "친구가 자기 API 키를 넣는 방법을 복사합니다." },
      { label: "AI 모델 저장", buttonId: "operatorBrainSave", note: "운용 직원 모델 설정을 저장합니다." },
    ],
  },
};

let buttonHelpBound = false;
let buttonHintTimer = null;
let buttonActionSeq = 0;

function buttonLabel(button) {
  return String(button?.textContent || button?.getAttribute("aria-label") || button?.id || "버튼").replace(/\s+/g, " ").trim();
}

function buttonHelp(button) {
  if (!button) return "";
  if (BUTTON_HELP[button.id]) return BUTTON_HELP[button.id];
  if (button.dataset.capitalPhaseTrain) return "선택한 구간만 다시 훈련하고 진행률과 결과를 갱신합니다.";
  if (button.dataset.hundredLabRun === "quick") return "빠르게 작동 상태와 가벼운 전략 후보를 확인합니다.";
  if (button.dataset.hundredLabRun === "focus") return "여러 전략 후보를 균형 있게 비교합니다. 평소 기본 선택입니다.";
  if (button.dataset.hundredLabRun === "ultra") return "시간을 더 써서 깊게 탐색합니다. 장외나 야간에 적합합니다.";
  if (button.dataset.pageJump) return "해당 메뉴로 이동합니다.";
  if (button.dataset.applyOptimized) return "검증에서 찾은 파라미터를 전략 입력칸에 적용합니다.";
  if (button.dataset.paperRehearsal) return "선택한 후보를 모의투자 리허설 티켓으로 만듭니다.";
  if (button.dataset.queueRehearsalReport) return "선택한 리허설 복기 보고를 큐에 넣습니다.";
  if (button.dataset.pilotTargetButton || button.dataset.competitiveButton) return "관련 버튼 위치를 화면에서 강조 표시합니다.";
  if (button.dataset.watchAdd) return "이 종목을 관심종목에 추가합니다.";
  if (button.dataset.watchRemove) return "이 종목을 관심종목에서 제거합니다.";
  if (button.dataset.addSymbol || button.dataset.replaySymbolPick || button.dataset.watchSelect) return "이 종목을 선택 목록에 추가합니다.";
  if (button.title && button.dataset.buttonHelpManaged !== "1") return button.title.split("\n")[0];
  const label = buttonLabel(button);
  return label ? `${label} 기능을 실행합니다. 결과는 해당 카드나 이벤트 로그에서 확인합니다.` : "버튼 기능을 실행합니다.";
}

function ensureButtonHelp(button) {
  if (!button) return "";
  const help = productText(buttonHelp(button));
  const label = buttonLabel(button);
  if (!button.title || button.dataset.buttonHelpManaged === "1") {
    button.title = help;
    button.dataset.buttonHelpManaged = "1";
  }
  if (label) button.setAttribute("aria-label", `${label}. ${help}`);
  return help;
}

function showButtonHint(button) {
  if (!button || button.closest(".tabs") || button.id === "agentConsoleMinimize") return;
  const help = ensureButtonHelp(button);
  const label = buttonLabel(button);
  if (!help || !label) return;
  let toast = el("#buttonHintToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "buttonHintToast";
    toast.className = "button-hint-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = `${label}: ${help}`;
  toast.classList.add("show");
  button.classList.add("button-pressed-feedback");
  window.clearTimeout(buttonHintTimer);
  buttonHintTimer = window.setTimeout(() => toast.classList.remove("show"), 2600);
  window.setTimeout(() => button.classList.remove("button-pressed-feedback"), 650);
}

function updateLastActionBoard(button, stateName = "idle", label = "대기") {
  const node = el("#workspaceLastAction");
  if (!node || !button) return;
  const time = new Date().toLocaleTimeString("ko-KR", { hour12: false });
  const help = ensureButtonHelp(button);
  node.className = `workspace-last-action ${stateName || "idle"}`;
  node.innerHTML = `
    <strong>최근 실행</strong>
    <span><b>${productHtml(buttonLabel(button))}</b> · ${productHtml(label)} · ${escapeHtml(time)}</span>
    <small>${productHtml(help)}</small>
  `;
}

function markButtonRunState(button, stateName, label) {
  if (!button) return;
  button.dataset.runState = stateName;
  button.dataset.runStateLabel = label;
  button.setAttribute("aria-busy", ["running", "pending"].includes(stateName) ? "true" : "false");
  button.setAttribute("aria-live", "polite");
  updateLastActionBoard(button, stateName, label);
}

function clearButtonRunState(button, delay = 4200) {
  if (!button) return;
  window.setTimeout(() => {
    delete button.dataset.runState;
    delete button.dataset.runStateLabel;
    button.removeAttribute("aria-busy");
  }, delay);
}

const INSTANT_NAVIGATION_SELECTOR = [
  "[data-instant-navigation]",
  ".tab",
  "[data-page-jump]",
  "[data-guide-button]",
  "[data-account-tab]",
].join(",");

function isInstantNavigationButton(button) {
  return Boolean(button?.matches(INSTANT_NAVIGATION_SELECTOR));
}

function clearInstantNavigationRunState(root = document) {
  root.querySelectorAll(INSTANT_NAVIGATION_SELECTOR).forEach((button) => {
    delete button.dataset.runState;
    delete button.dataset.runStateLabel;
    delete button.dataset.actionSeq;
    delete button.dataset.actionStartedAt;
    button.removeAttribute("aria-busy");
    button.removeAttribute("aria-live");
  });
}

function startButtonRunState(button) {
  if (!button || button.disabled || isInstantNavigationButton(button) || button.closest(".tabs") || button.dataset.guideButton || button.id === "agentConsoleMinimize") return;
  const seq = ++buttonActionSeq;
  button.dataset.actionSeq = String(seq);
  button.dataset.actionStartedAt = String(Date.now());
  markButtonRunState(button, "running", "실행중");
  window.setTimeout(() => {
    if (button.dataset.actionSeq === String(seq) && button.dataset.runState === "running") {
      markButtonRunState(button, "pending", "확인중");
    }
  }, 1200);
  window.setTimeout(() => {
    if (button.dataset.actionSeq === String(seq) && ["running", "pending"].includes(button.dataset.runState || "")) {
      markButtonRunState(button, "done", "로그 확인");
      clearButtonRunState(button);
    }
  }, 6200);
}

const BUTTON_RUN_GENERIC_TOKENS = new Set([
  "button",
  "btn",
  "api",
  "실행",
  "조회",
  "새로고침",
  "갱신",
  "확인",
  "보기",
  "열기",
  "복사",
  "저장",
  "시작",
  "정지",
  "적용",
  "결과",
]);

function normalizeButtonRunText(value) {
  return productText(String(value || ""))
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function buttonRunMessageRelated(button, text) {
  const normalized = normalizeButtonRunText(text);
  const label = normalizeButtonRunText(`${buttonLabel(button)} ${button.id || ""} ${button.dataset.actionName || ""}`);
  if (!normalized || !label) return false;
  const compactText = normalized.replace(/\s+/g, "");
  const compactLabel = label.replace(/\s+/g, "");
  if (compactLabel.length >= 2 && compactText.includes(compactLabel)) return true;
  const tokens = label
    .split(/[^0-9a-zA-Z가-힣]+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 2 && !BUTTON_RUN_GENERIC_TOKENS.has(token));
  return tokens.some((token) => normalized.includes(token));
}

function isBackgroundButtonRunLog(text) {
  const normalized = normalizeButtonRunText(text);
  if (!normalized) return false;
  return (
    /poll|refresh|background|heartbeat|cache/.test(normalized)
    || /(자동|백그라운드|갱신|상태|기록|카드|랭킹|레이더|스크리너|섹터|뉴스).*(실패|오류|에러|failed|error)/i.test(normalized)
    || /(실패|오류|에러|failed|error).*(자동|백그라운드|갱신|상태|기록|카드|랭킹|레이더|스크리너|섹터|뉴스)/i.test(normalized)
  );
}

function resolveLatestButtonRunState(message) {
  const button = document.querySelector(`button[data-action-seq="${buttonActionSeq}"]`);
  if (!button) return;
  const startedAt = Number(button.dataset.actionStartedAt || 0);
  const elapsed = Date.now() - startedAt;
  if (!startedAt || elapsed > 18000) return;
  const text = String(message || "");
  const related = buttonRunMessageRelated(button, text);
  const background = isBackgroundButtonRunLog(text);
  if (/실패|오류|에러|차단|불가|거절|중단|failed|error/i.test(text)) {
    if (!related && (background || elapsed > 3500)) return;
    markButtonRunState(button, "fail", "실패");
    clearButtonRunState(button, 6200);
    return;
  }
  if (/완료|성공|저장|갱신|조회|등록|생성|전송|적용|확인|시작|정지|큐|통과/i.test(text)) {
    if (!related && (background || elapsed > 3500)) return;
    markButtonRunState(button, "success", "완료");
    clearButtonRunState(button);
  }
}

function setupButtonHelp() {
  clearInstantNavigationRunState();
  document.querySelectorAll("button").forEach(ensureButtonHelp);
  if (buttonHelpBound) return;
  document.addEventListener("mouseover", (event) => {
    const button = event.target.closest("button");
    if (button) ensureButtonHelp(button);
  }, true);
  document.addEventListener("focusin", (event) => {
    const button = event.target.closest("button");
    if (button) ensureButtonHelp(button);
  }, true);
  document.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (button) {
      showButtonHint(button);
      startButtonRunState(button);
    }
  }, true);
  buttonHelpBound = true;
}

function renderPageActionGuide(pageId) {
  const node = el("#workspaceCurrentActions");
  if (!node) return;
  const guide = PAGE_ACTION_GUIDE[pageId] || PAGE_ACTION_GUIDE.dashboard;
  const actionHtml = guide.actions.map((action, index) => {
    const help = BUTTON_HELP[action.buttonId] || action.note || "이 기능을 실행합니다.";
    const targetExists = Boolean(document.getElementById(action.buttonId));
    return `
      <article class="workspace-action-card ${targetExists ? "ready" : "missing"}">
        <b>${index + 1}</b>
        <div>
          <strong>${productHtml(action.label)}</strong>
          <span>${productHtml(action.note)}</span>
          <small>${productHtml(help)}</small>
        </div>
        <button type="button" data-guide-button="${escapeHtml(action.buttonId)}" ${targetExists ? "" : "disabled"}>${targetExists ? "위치 보기" : "버튼 확인중"}</button>
      </article>
    `;
  }).join("");
  node.innerHTML = `
    <div class="workspace-action-head">
      <strong>${productHtml(guide.headline)}</strong>
      <span>${productHtml(guide.safety)}</span>
    </div>
    <div class="workspace-action-grid">${actionHtml}</div>
  `;
  setupButtonHelp();
}

function programIntroText() {
  return [
    "# 코덱스스톡 소개",
    "",
    "코덱스스톡은 로컬 PC에서 실행되는 한국어 AI 주식 운용실입니다. 단순 차트 앱이 아니라 AI 연구원, AI 운용직원, 리스크 관리자, HTS형 대시보드를 하나로 묶어 시장 분석, 전략 검증, 모의훈련, 실전 후보 관리를 돕는 프로그램입니다.",
    "",
    "## 핵심 목적",
    "- 사용자가 하루 종일 HTS/MTS를 보지 않아도 AI가 24시간 시장을 연구하고 기록합니다.",
    "- AI는 뉴스, 공시, 재무, 거시지표, 가격 흐름, 거래량, 섹터 흐름을 계속 확인합니다.",
    "- 사용자는 PC 대시보드와 텔레그램으로 상황을 보고받고 명령할 수 있습니다.",
    "- 실전 주문은 안전 게이트, 승인, 한도, 긴급정지 구조를 거치도록 설계되어 있습니다.",
    "",
    "## 구현된 기능",
    "- 대시보드: 계좌, 시장, API, 후보, 위험, 최근 로그를 한눈에 확인합니다.",
    "- AI 트레이더: 연구 직원과 운용 직원의 작업, 회의, 브리핑, 텔레그램 상태를 봅니다.",
    "- 추천 종목: 섹터별 후보, 추천 근거, 뉴스/재무 레이더, 기업 분석 카드를 봅니다.",
    "- AI 감독/승인: AI가 만든 후보와 실전 파일럿 티켓을 검토하고 승인/정지합니다.",
    "- 전략 연구: 날짜 지정 백테스트, 다중 종목 비교, 강건성 검증, 과거장 훈련을 실행합니다.",
    "- 100억 프로젝트: 2000년부터 현재까지 장기 성장 전략을 구간별로 훈련하고 기록합니다.",
    "- 설정/기록: AI 모델, API 연결, 리스크 설정, 배포 준비도, 운영 기록을 관리합니다.",
    "",
    "## 연결 구조",
    "- 한국투자증권 KIS, DART, 한국은행 ECOS, FRED, KRX 설정 구조를 갖고 있습니다.",
    "- 텔레그램 명령 확인과 보고 큐 구조가 있습니다.",
    "- 실계좌와 모의계좌를 분리해서 보는 구조가 있습니다.",
    "- API 키와 개인 정보는 소개문이나 화면에 직접 노출하지 않는 방향입니다.",
    "",
    "## 안전 원칙",
    "- 실전 주문은 기본적으로 잠금/승인 기반입니다.",
    "- 1회 주문한도, 일 손실정지, 종목 비중한도, 긴급정지, 중복 주문 방지 구조가 있습니다.",
    "- 백테스트와 과거장 훈련은 연구/검증용이며 실전 수익을 보장하지 않습니다.",
    "",
    "## 현재 개발 방향",
    "- 버튼이 많은 화면을 더 쉽게 쓰도록 메뉴별 핵심 행동 안내와 버튼 상태 표시를 강화했습니다.",
    "- 모든 종목은 가능하면 티커나 숫자보다 종목명 중심으로 보여주고 있습니다.",
    "- AI가 연구, 회의, 복기, 매매일지, 장기기억을 쌓으며 점점 주식 특화 지식망을 만드는 구조로 확장 중입니다.",
  ].join("\n");
}

function renderProgramIntro() {
  const node = el("#programIntroText");
  if (node) node.value = programIntroText();
}

async function copyProgramIntro() {
  const text = programIntroText();
  try {
    await copyTextToClipboard(text);
    setText("programIntroState", "복사 완료");
    addLog("코덱스스톡 소개문 복사 완료");
  } catch (error) {
    setText("programIntroState", "복사 실패");
    addLog(`코덱스스톡 소개문 복사 실패: ${error.message}`);
  }
}

function downloadProgramIntro() {
  try {
    const blob = new Blob([programIntroText()], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `codexstock-intro-${todayIso()}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setText("programIntroState", "저장 시작");
    addLog("코덱스스톡 소개문 Markdown 저장 시작");
  } catch (error) {
    setText("programIntroState", "저장 실패");
    addLog(`코덱스스톡 소개문 저장 실패: ${error.message}`);
  }
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "readonly");
  area.style.position = "fixed";
  area.style.left = "-9999px";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

function setFriendReleaseCommandState(message, level = "info") {
  setText("friendReleaseCommandState", message);
  const node = el("#friendReleaseCommandState");
  if (node) node.className = `release-command-state ${level}`;
}

async function copyFriendReleaseCommand() {
  try {
    const readiness = await ensureFriendReleaseReadiness();
    if (!readiness.ready) {
      setFriendReleaseCommandState("차단/주의 항목 먼저 확인", "warning");
      addLog(`친구용 패키지 생성 명령 복사 차단: ${readiness.status || "배포 준비도 추가 확인 필요"}`);
      return;
    }
    const command = el("#friendReleaseCommand")?.textContent?.trim() || ".\\prepare_friend_release.ps1";
    await copyTextToClipboard(command);
    setFriendReleaseCommandState("복사 완료", "success");
    addLog("친구용 패키지 생성 명령 복사 완료");
  } catch (error) {
    setFriendReleaseCommandState("복사 실패", "danger");
    addLog(`친구용 패키지 생성 명령 복사 실패: ${error.message}`);
  }
}

function friendUsageGuideText() {
  return [
    "코덱스스톡 친구용 첫 사용 안내",
    "",
    "1. 프로그램은 받은 폴더 안에서 실행하면 됩니다.",
    "2. 한국투자증권, DART, ECOS, FRED, KRX 같은 API 키는 각자 본인 이름으로 직접 발급해야 합니다.",
    "3. 내 API 키나 계좌 토큰은 공유하면 안 됩니다. 친구마다 자기 키를 넣어야 합니다.",
    "4. 처음 실행하면 설정/기록 메뉴에서 API 연결 상태를 먼저 확인하세요.",
    "5. 실전 주문은 기본적으로 잠금/승인 구조입니다. 처음에는 모의투자와 백테스트부터 확인하세요.",
    "6. 텔레그램을 쓰려면 친구 본인의 봇 토큰과 채팅 ID를 설정해야 합니다.",
    "7. 자동매매를 켜기 전에는 1회 주문한도, 하루 손실정지, 종목 비중한도, 긴급정지를 꼭 확인하세요.",
    "8. 코덱스스톡은 수익을 보장하지 않습니다. AI 연구, 후보 발굴, 백테스트, 복기, 리스크 관리 보조 도구입니다.",
    "",
    "추천 첫 순서:",
    "- 대시보드에서 전체 상태 확인",
    "- 설정/기록에서 API 상태 확인",
    "- 추천 종목에서 후보 공부",
    "- 전략 연구에서 백테스트 실행",
    "- AI 감독/승인에서 후보와 안전 게이트 확인",
    "- 실전 주문은 충분히 확인한 뒤 아주 작은 수량부터 테스트",
  ].join("\n");
}

async function copyFriendUsageGuide() {
  try {
    await copyTextToClipboard(friendUsageGuideText());
    setFriendReleaseCommandState("친구 사용법 복사 완료", "success");
    addLog("친구용 첫 사용 안내문 복사 완료");
  } catch (error) {
    setFriendReleaseCommandState("친구 사용법 복사 실패", "danger");
    addLog(`친구용 첫 사용 안내문 복사 실패: ${error.message}`);
  }
}

function apiSetupGuideText() {
  return [
    "코덱스스톡 API 설정 안내",
    "",
    "중요: API 키와 계좌 토큰은 절대 다른 사람 것과 공유하지 말고, 각자 본인 명의로 발급해서 넣어야 합니다.",
    "",
    "1. 배포받은 폴더에서 설정 예시 파일을 찾습니다.",
    "- 보통 .env.example 또는 config 예시 파일을 참고합니다.",
    "- 실제 비밀값은 .env 같은 개인 설정 파일에만 넣습니다.",
    "",
    "2. 필요한 API를 본인 명의로 발급합니다.",
    "- 한국투자증권 KIS: 국내/해외 주식 시세, 계좌, 주문 연동용",
    "- DART: 기업 공시 조회용",
    "- 한국은행 ECOS: 국내 거시지표 조회용",
    "- FRED: 미국 거시지표 조회용",
    "- KRX: 국내 시장 데이터 보강용",
    "- 텔레그램 Bot Token/Chat ID: 명령과 보고용",
    "",
    "3. 처음에는 실전 주문을 켜지 않습니다.",
    "- API 상태 확인",
    "- 모의투자 확인",
    "- 백테스트 확인",
    "- 텔레그램 보고 확인",
    "- 그 다음 아주 작은 수량으로만 실전 테스트",
    "",
    "4. 실전 주문 전 반드시 확인할 것",
    "- 실전 실행 스위치가 의도한 상태인지",
    "- 1회 주문한도",
    "- 하루 손실정지",
    "- 종목 비중한도",
    "- 긴급정지 버튼 위치",
    "- 텔레그램 명령이 정상 응답하는지",
    "",
    "5. 친구에게 절대 보내면 안 되는 것",
    "- 내 .env 파일",
    "- 내 계좌번호/토큰",
    "- 내 텔레그램 봇 토큰",
    "- 실전 주문 로그가 포함된 개인 기록",
    "- 캐시나 임시 파일 안의 개인 데이터",
  ].join("\n");
}

async function copyApiSetupGuide() {
  try {
    await copyTextToClipboard(apiSetupGuideText());
    setFriendReleaseCommandState("API 설정 안내 복사 완료", "success");
    addLog("친구용 API 설정 안내문 복사 완료");
  } catch (error) {
    setFriendReleaseCommandState("API 설정 안내 복사 실패", "danger");
    addLog(`친구용 API 설정 안내문 복사 실패: ${error.message}`);
  }
}

function releaseReadinessSummaryText(data = state.friendReleaseReadiness) {
  if (!data) {
    return [
      "코덱스스톡 친구 배포 준비도",
      "",
      "아직 점검 결과가 없습니다.",
      "설정/기록 > 친구 배포 준비도에서 '다시 점검'을 먼저 눌러주세요.",
    ].join("\n");
  }
  const summary = data.summary || {};
  const checks = Array.isArray(data.checks) ? data.checks : [];
  const envKeys = Array.isArray(data.env_keys) ? data.env_keys : [];
  const blockerChecks = checks.filter((item) => item.status === "blocker");
  const warningChecks = checks.filter((item) => item.status === "warning");
  const passChecks = checks.filter((item) => item.status === "pass");
  const lineFor = (item) => {
    const path = item.path ? ` (${item.path})` : "";
    const action = item.action ? ` / 조치: ${item.action}` : "";
    return `- ${item.label || "점검 항목"}: ${item.detail || "-"}${path}${action}`;
  };
  return [
    "코덱스스톡 친구 배포 준비도 점검 결과",
    "",
    `점검 시각: ${state.friendReleaseCheckedAt || "확인 안 됨"}`,
    `상태: ${data.status || "점검 필요"}`,
    `점수: ${Math.round(Number(data.score || 0))}점`,
    `배포 가능 여부: ${data.ready ? "가능" : "추가 확인 필요"}`,
    `프로젝트 내부 유출: ${summary.repo_private_files ?? summary.private_files ?? 0}개`,
    `배포본 유출: ${summary.dist_private_files ?? 0}개`,
    `외부 런타임으로 안전 분리: ${summary.runtime_private_files ?? 0}개`,
    `설정 예시: ${envKeys.filter((item) => item.present_in_example).length}/${envKeys.length || 0}`,
    `배포 폴더: ${summary.dist_exists ? "있음" : "없음"}`,
    `생성 명령: ${data.release_command || ".\\prepare_friend_release.ps1"}`,
    "",
    `차단 항목 ${blockerChecks.length}개`,
    ...(blockerChecks.length ? blockerChecks.map(lineFor) : ["- 없음"]),
    "",
    `주의 항목 ${warningChecks.length}개`,
    ...(warningChecks.length ? warningChecks.map(lineFor) : ["- 없음"]),
    "",
    `통과 항목 ${passChecks.length}개`,
    ...(passChecks.length ? passChecks.slice(0, 8).map(lineFor) : ["- 없음"]),
    "",
    "공유 전 확인:",
    "- 내 .env, 계좌 토큰, 텔레그램 토큰, 실전 주문 로그는 친구에게 보내지 않습니다.",
    "- 친구는 자기 API 키를 직접 발급해서 설정해야 합니다.",
  ].join("\n");
}

async function copyReleaseReadinessSummary() {
  try {
    await ensureFriendReleaseReadiness();
    await copyTextToClipboard(releaseReadinessSummaryText());
    setFriendReleaseCommandState("점검 결과 복사 완료", "success");
    addLog("친구 배포 준비도 점검 결과 복사 완료");
  } catch (error) {
    setFriendReleaseCommandState("점검 결과 복사 실패", "danger");
    addLog(`친구 배포 준비도 점검 결과 복사 실패: ${error.message}`);
  }
}

async function downloadReleaseReadinessSummary() {
  try {
    await ensureFriendReleaseReadiness();
    const blob = new Blob([releaseReadinessSummaryText()], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `codexstock-release-check-${todayIso()}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setFriendReleaseCommandState("점검 결과 저장 시작", "info");
    addLog("친구 배포 준비도 점검 결과 Markdown 저장 시작");
  } catch (error) {
    setFriendReleaseCommandState("점검 결과 저장 실패", "danger");
    addLog(`친구 배포 준비도 점검 결과 저장 실패: ${error.message}`);
  }
}

function friendSharePackText() {
  return [
    "# 코덱스스톡 친구 공유 안내 묶음",
    "",
    `생성일: ${new Date().toLocaleString("ko-KR", { hour12: false })}`,
    "",
    "---",
    "",
    programIntroText(),
    "",
    "---",
    "",
    friendUsageGuideText(),
    "",
    "---",
    "",
    apiSetupGuideText(),
    "",
    "---",
    "",
    releaseReadinessSummaryText(),
  ].join("\n");
}

async function copyFriendSharePack() {
  try {
    await ensureFriendReleaseReadiness();
    await copyTextToClipboard(friendSharePackText());
    setFriendReleaseCommandState("친구 안내 묶음 복사 완료", "success");
    addLog("친구 안내 묶음 클립보드 복사 완료");
  } catch (error) {
    setFriendReleaseCommandState("친구 안내 묶음 복사 실패", "danger");
    addLog(`친구 안내 묶음 복사 실패: ${error.message}`);
  }
}

async function downloadFriendSharePack() {
  try {
    await ensureFriendReleaseReadiness();
    const blob = new Blob([friendSharePackText()], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `codexstock-friend-guide-pack-${todayIso()}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setFriendReleaseCommandState("친구 안내 묶음 저장 시작", "success");
    addLog("친구 안내 묶음 Markdown 저장 시작");
  } catch (error) {
    setFriendReleaseCommandState("친구 안내 묶음 저장 실패", "danger");
    addLog(`친구 안내 묶음 저장 실패: ${error.message}`);
  }
}

async function ensureFriendReleaseReadiness() {
  const checkedAgeMs = Date.now() - Number(state.friendReleaseCheckedAtMs || 0);
  const stale = state.friendReleaseReadiness && (!state.friendReleaseCheckedAtMs || checkedAgeMs > 10 * 60 * 1000);
  if (state.friendReleaseReadiness && !stale) return state.friendReleaseReadiness;
  setFriendReleaseCommandState(stale ? "오래된 결과 재점검 중" : "먼저 점검 중", stale ? "warning" : "info");
  await loadFriendReleaseReadiness();
  if (!state.friendReleaseReadiness) throw new Error("친구 배포 준비도 점검 결과가 없습니다.");
  return state.friendReleaseReadiness;
}

function todayIso() {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

function fileSafeToken(value = "", fallback = "record") {
  return String(value || fallback)
    .trim()
    .replace(/[\\/:*?"<>|\s]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80) || fallback;
}

function syncDefaultDates() {
  const endNode = el("#endDate");
  const startNode = el("#startDate");
  if (!endNode) return;
  const today = todayIso();
  endNode.max = today;
  if (!endNode.value || endNode.value < today) endNode.value = today;
  if (startNode && (!startNode.value || startNode.value >= endNode.value)) startNode.value = "2016-01-01";
}

function setText(id, value) {
  const node = el(`#${id}`);
  if (node) node.textContent = productText(value);
}

function setInputIfIdle(id, value) {
  const node = el(`#${id}`);
  if (!node || document.activeElement === node) return;
  node.value = value ?? "";
}

function readNumberInput(id, fallback = 0) {
  const value = Number(el(`#${id}`)?.value);
  return Number.isFinite(value) ? value : fallback;
}

function capitalRiskLevel(value) {
  const pctValue = Number(value || 0);
  if (pctValue >= 80) return { level: "danger", label: "위험", detail: "위험: 80% 이상은 계좌 변동성이 커서 사용자 확인이 필요합니다." };
  if (pctValue >= 50) return { level: "warning", label: "주의", detail: "주의: 50% 이상은 적극 운용 구간입니다. 승인 게이트와 중복주문 차단을 유지합니다." };
  return { level: "good", label: "양호", detail: "양호: 30% 안팎은 기본 자율 운용 구간으로 관리합니다." };
}

function applyCapitalRiskInputState(id, value) {
  const node = el(`#${id}`);
  if (!node) return null;
  const risk = capitalRiskLevel(value);
  node.classList.remove("ops-risk-good", "ops-risk-warning", "ops-risk-danger");
  node.classList.add(`ops-risk-${risk.level}`);
  node.title = risk.label;
  node.setAttribute("aria-label", `${node.closest("label")?.textContent?.trim() || id}: ${risk.label}`);
  node.closest("label")?.setAttribute("title", risk.label);
  return risk;
}

function updateOpsCapitalRiskBadge(policy = {}) {
  const node = el("#opsCapitalRiskBadge");
  if (!node) return;
  const autoPct = readNumberInput("opsPolicyAutoCashPct", Number(policy.delegated_live_auto_submit_max_cash_pct ?? 30));
  const approvalPct = readNumberInput("opsPolicyApprovalCashPct", Number(policy.delegated_live_user_approval_above_cash_pct ?? 50));
  const dynamicPct = readNumberInput("opsPolicyDynamicMaxCashPct", Number(policy.live_pilot_dynamic_max_cash_pct ?? policy.live_pilot_max_cash_pct ?? 50));
  const pilotPct = readNumberInput("opsPolicyPilotCashPct", Number(policy.live_pilot_max_cash_pct ?? 30));
  applyCapitalRiskInputState("opsPolicyAutoCashPct", autoPct);
  applyCapitalRiskInputState("opsPolicyApprovalCashPct", approvalPct);
  applyCapitalRiskInputState("opsPolicyDynamicMaxCashPct", dynamicPct);
  applyCapitalRiskInputState("opsPolicyPilotCashPct", pilotPct);
  const highestPct = Math.max(autoPct, approvalPct, dynamicPct, pilotPct);
  const risk = capitalRiskLevel(highestPct);
  node.className = `ops-capital-risk ${risk.level}`;
  node.title = risk.label;
  node.setAttribute("aria-label", `자금 운용 ${risk.label}`);
  node.innerHTML = `
    <b>자금 운용 <i>${risk.label}</i></b>
    <span><em class="ops-risk-dot good" title="양호">30% 양호</em><em class="ops-risk-dot warning" title="주의">50% 주의</em><em class="ops-risk-dot danger" title="위험">80% 위험</em></span>
    <span>AI ${autoPct.toFixed(1)}% / 승인 ${approvalPct.toFixed(1)}% / 최대 ${dynamicPct.toFixed(1)}%</span>
    <small>${risk.detail}</small>
  `;
}

function cleanAppName(value) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, 32);
}

function savedAppName() {
  try {
    return cleanAppName(localStorage.getItem(APP_NAME_STORAGE_KEY)) || t.appTitle;
  } catch (_) {
    return t.appTitle;
  }
}

function applyAppName(value = savedAppName()) {
  const name = cleanAppName(value) || t.appTitle;
  const node = el("#appTitle");
  if (node) {
    node.textContent = name;
    node.title = "더블클릭해서 프로그램 이름 변경";
    node.setAttribute("aria-label", `${name} 프로그램 이름. 더블클릭하면 변경할 수 있습니다.`);
  }
  document.title = `${name} HTS`;
  return name;
}

function saveAppName(value) {
  const name = cleanAppName(value) || t.appTitle;
  try {
    localStorage.setItem(APP_NAME_STORAGE_KEY, name);
  } catch (_) {}
  return applyAppName(name);
}

function beginAppNameEdit() {
  const node = el("#appTitle");
  if (!node || node.dataset.editing === "1") return;
  node.dataset.editing = "1";
  node.dataset.previousName = node.textContent || savedAppName();
  node.contentEditable = "plaintext-only";
  node.classList.add("editing");
  node.textContent = "";
  node.focus();
}

function finishAppNameEdit(commit = true) {
  const node = el("#appTitle");
  if (!node || node.dataset.editing !== "1") return;
  const previous = node.dataset.previousName || t.appTitle;
  const next = commit ? cleanAppName(node.textContent) || previous : previous;
  node.dataset.editing = "0";
  node.contentEditable = "false";
  node.classList.remove("editing");
  delete node.dataset.previousName;
  saveAppName(next);
}

function defaultTabOrder() {
  return Array.from(document.querySelectorAll(".tabs .tab")).map((tab) => tab.dataset.page).filter(Boolean);
}

function readTabOrder() {
  try {
    const saved = JSON.parse(localStorage.getItem(TAB_ORDER_STORAGE_KEY) || "[]");
    return Array.isArray(saved) ? saved.map(String).filter(Boolean) : [];
  } catch (_) {
    return [];
  }
}

function saveTabOrder() {
  const order = defaultTabOrder();
  try {
    localStorage.setItem(TAB_ORDER_STORAGE_KEY, JSON.stringify(order));
  } catch (_) {}
}

function restoreTabOrder() {
  const tabs = el(".tabs");
  if (!tabs) return;
  const buttons = Array.from(tabs.querySelectorAll(".tab"));
  const byPage = new Map(buttons.map((button) => [button.dataset.page, button]));
  const saved = readTabOrder();
  const orderedPages = [...saved, ...buttons.map((button) => button.dataset.page)].filter((page, index, rows) => page && rows.indexOf(page) === index);
  orderedPages.forEach((page) => {
    const button = byPage.get(page);
    if (button) tabs.appendChild(button);
  });
}

function tabAfterDragTarget(container, y) {
  const candidates = Array.from(container.querySelectorAll(".tab:not(.dragging)"));
  return candidates.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) return { offset, element: child };
    return closest;
  }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
}

function bindTabOrderControls() {
  const tabs = el(".tabs");
  if (!tabs) return;
  restoreTabOrder();
  Array.from(tabs.querySelectorAll(".tab")).forEach((tab) => {
    tab.draggable = true;
    tab.title = "잡고 위아래로 끌어서 메뉴 순서를 바꿀 수 있습니다.";
    tab.addEventListener("dragstart", () => {
      tab.classList.add("dragging");
      tab.dataset.dragMoved = "0";
    });
    tab.addEventListener("dragend", () => {
      const moved = tab.dataset.dragMoved === "1";
      tab.classList.remove("dragging");
      window.setTimeout(() => { tab.dataset.dragMoved = "0"; }, 0);
      saveTabOrder();
      if (moved) addLog("왼쪽 메뉴 탭 순서를 저장했습니다.");
    });
  });
  tabs.addEventListener("dragover", (event) => {
    event.preventDefault();
    const dragging = tabs.querySelector(".tab.dragging");
    if (!dragging) return;
    dragging.dataset.dragMoved = "1";
    const after = tabAfterDragTarget(tabs, event.clientY);
    if (after) tabs.insertBefore(dragging, after);
    else tabs.appendChild(dragging);
  });
}

function normalizeSymbol(value) {
  const normalized = String(value || "").trim().toUpperCase();
  if (/^\d{1,6}$/.test(normalized)) return normalized.padStart(6, "0");
  return normalized;
}

function compactSearchText(value) {
  return String(value || "").trim().toUpperCase().replace(/\s+/g, "");
}

function usefulSymbolName(value, symbol) {
  const text = String(value || "").trim();
  return text && text.toUpperCase() !== String(symbol || "").toUpperCase();
}

const pointInTimeSymbolNameRules = {
  "000660": [
    { from: "1900-01-01", to: "2001-03-21", name: "\ud604\ub300\uc804\uc790" },
    { from: "2001-03-22", to: "2011-12-31", name: "\ud558\uc774\ub2c9\uc2a4\ubc18\ub3c4\uccb4" },
    { from: "2012-01-01", to: "9999-12-31", name: "SK\ud558\uc774\ub2c9\uc2a4" },
  ],
};

function pointInTimeDateKey(value = "") {
  const text = String(value || "").trim();
  const dateMatch = text.match(/\d{4}-\d{2}-\d{2}/);
  if (dateMatch) return dateMatch[0];
  const yearMatch = text.match(/\d{4}/);
  return yearMatch ? `${yearMatch[0]}-01-01` : "";
}

function pointInTimeSymbolName(symbol, atDate = "", quote = null) {
  const normalized = normalizeSymbol(symbol || quote?.symbol || "");
  if (quote?.historical_name && usefulSymbolName(quote.historical_name, normalized)) return String(quote.historical_name);
  const currentName = symbolDisplayName(normalized, { ...(quote || {}), historical_name: "" });
  const dateKey = pointInTimeDateKey(atDate || quote?.entry_date || quote?.date || quote?.name_as_of_date);
  const rules = pointInTimeSymbolNameRules[normalized] || [];
  const matched = rules.find((rule) => (!rule.from || rule.from <= dateKey) && (!rule.to || dateKey <= rule.to));
  return matched?.name || currentName || normalized;
}

function pointInTimeDisplayName(symbol, atDate = "", quote = null) {
  const normalized = normalizeSymbol(symbol || quote?.symbol || "");
  const historicalName = pointInTimeSymbolName(normalized, atDate, quote);
  const currentName = quote?.current_name && usefulSymbolName(quote.current_name, normalized)
    ? String(quote.current_name)
    : symbolDisplayName(normalized, { ...(quote || {}), historical_name: "" });
  if (historicalName && currentName && historicalName !== currentName) return `${historicalName}(\ud604 ${currentName})`;
  return historicalName || currentName || normalized;
}

const productLikeDisplaySymbols = new Set([
  "SPY", "QQQ", "DIA", "IWM", "VOO", "IVV", "VTI", "VT", "VEA", "VWO", "SCHD",
  "TQQQ", "SQQQ", "SOXL", "SOXS", "NVDL", "NVDS", "TSLL", "TSLS", "BITO", "BITX",
]);
const productLikeCompactNamePrefixes = ["KODEX", "TIGER", "KBSTAR", "HANARO", "ARIRANG", "KOSEF", "TIMEFOLIO"];
const productLikeStrictNamePrefixes = ["RISE", "ACE", "SOL", "PLUS"];

function isProductLikeSecurity(symbol, ...descriptors) {
  const normalized = normalizeSymbol(symbol || "");
  if (productLikeDisplaySymbols.has(normalized)) return true;
  const text = descriptors.filter((item) => item !== undefined && item !== null).map((item) => String(item)).join(" ").toUpperCase();
  if (!text) return false;
  if (/\b(ETF|ETN|ETP|UCITS)\b/.test(text)) return true;
  if (/\b(EXCHANGE[- ]TRADED|INDEX FUND|ETF TRUST|INDEX TRUST)\b/.test(text)) return true;
  const strictMatch = productLikeStrictNamePrefixes.some((prefix) => (
    text === prefix
    || text.startsWith(`${prefix} `)
    || text.includes(` ${prefix} `)
  ));
  const compactMatch = productLikeCompactNamePrefixes.some((prefix) => text.startsWith(prefix) || text.includes(` ${prefix}`));
  return strictMatch || compactMatch;
}

function symbolMeta(symbol, quote = null) {
  const normalized = normalizeSymbol(symbol || quote?.symbol || "");
  const quoteRow = quote || state.quotes.get(normalized) || {};
  const watchRow = (state.watchlist || []).find((row) => normalizeSymbol(row.symbol) === normalized) || {};
  const universeRow = researchUniverse.find((row) => normalizeSymbol(row.symbol) === normalized) || {};
  const knownDisplayNames = {
    SPY: "S&P 500 ETF",
    QQQ: "나스닥 100 ETF",
    DIA: "다우존스 ETF",
    IWM: "러셀 2000 ETF",
    AAPL: "애플",
    MSFT: "마이크로소프트",
    NVDA: "엔비디아",
    TSLA: "테슬라",
    GOOGL: "알파벳",
    AMZN: "아마존",
    AMD: "어드밴스드 마이크로 디바이시스",
    META: "메타",
    TSM: "TSMC",
    AVGO: "브로드컴",
    "BRK.B": "버크셔 해서웨이",
    JPM: "JP모건",
    V: "비자",
    MA: "마스터카드",
    LLY: "일라이 릴리",
    COST: "코스트코",
  };
  const sourceName = [quoteRow.display_name, quoteRow.name, watchRow.display_name, watchRow.name, universeRow.display_name, universeRow.name].find((item) => usefulSymbolName(item, normalized));
  const candidateName = knownDisplayNames[normalized]
    || sourceName
    || (/^\d{6}$/.test(normalized) ? "종목명 확인 중" : normalized);
  const name = isProductLikeSecurity(
    normalized,
    candidateName,
    quoteRow.security_type,
    quoteRow.type,
    quoteRow.market,
    watchRow.market,
    universeRow.market,
  )
    ? normalized
    : candidateName;
  return {
    symbol: normalized,
    name: String(name || normalized),
    market: quoteRow.market || watchRow.market || universeRow.market || (/^\d{6}$/.test(normalized) ? "KR" : "US"),
    choseong: universeRow.choseong || watchRow.choseong || getChoseong(name || normalized),
  };
}

function symbolSubLabel(meta) {
  return [meta.market].filter(Boolean).join(" · ") || "시장 확인";
}

function symbolDisplayName(symbol, quote = null) {
  return symbolMeta(symbol, quote).name;
}

function rowDisplayName(row = {}) {
  return symbolMeta(row.symbol, row).name;
}

function replaceSymbolCodesInText(value) {
  const raw = String(value || "");
  if (!raw) return raw;
  const upper = raw.toUpperCase();
  const replacements = new Map();
  const pushReplacement = (row = {}) => {
    const symbol = normalizeSymbol(row.symbol);
    if (!symbol || !upper.includes(symbol.toUpperCase())) return;
    const directName = symbolDisplayName(symbol, row);
    const name = String(directName || "").trim();
    if (!symbol || !name || name === symbol || name === "종목명 확인 중") return;
    replacements.set(symbol, name);
  };
  symbols.forEach((symbol) => pushReplacement({ symbol, name: symbolDisplayName(symbol) }));
  (state.selectedResearchSymbols || []).forEach((symbol) => pushReplacement({ symbol, name: symbolDisplayName(symbol) }));
  (state.replaySelectedSymbols || []).forEach((symbol) => pushReplacement({ symbol, name: symbolDisplayName(symbol) }));
  (state.watchlist || []).forEach(pushReplacement);
  (state.recommendations || []).forEach(pushReplacement);
  (state.lastCandidates || []).forEach(pushReplacement);
  return Array.from(replacements.entries())
    .sort((a, b) => b[0].length - a[0].length)
    .reduce((text, [symbol, name]) => {
      const escaped = symbol.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return text
        .replace(new RegExp(`\\(${escaped}\\)`, "g"), "")
        .replace(new RegExp(`\\b${escaped}\\b`, "g"), name);
    }, raw);
}

function searchableUniverse() {
  const seen = new Set();
  const rows = [];
  const push = (row) => {
    const symbol = normalizeSymbol(row?.symbol);
    if (!symbol || seen.has(symbol)) return;
    seen.add(symbol);
    const meta = symbolMeta(symbol, row);
    rows.push({
      symbol,
      name: usefulSymbolName(row?.name, symbol) ? row.name : meta.name,
      market: row?.market || meta.market,
      choseong: row?.choseong || meta.choseong,
    });
  };
  researchUniverse.forEach(push);
  (state.watchlist || []).forEach(push);
  symbols.forEach((symbol) => push(symbolMeta(symbol)));
  (state.recommendations || []).forEach(push);
  return rows;
}

function setTabLabel(id, pageId) {
  const node = el(`#${id}`);
  const guide = pageGuide[pageId];
  if (!node || !guide) return;
  node.innerHTML = `<span>${escapeHtml(guide.title)}</span><small>${escapeHtml(guide.tab)}</small>`;
  node.title = `${guide.title}: ${guide.desc}`;
}

function localize() {
  applyAppName();
  setTabLabel("tabDashboard", "dashboard");
  setTabLabel("tabTrading", "trading");
  setTabLabel("tabResearch", "research");
  setTabLabel("tabAiTrader", "aiTrader");
  setTabLabel("tabRecommendations", "recommendations");
  setTabLabel("tabCapitalChallenge", "capitalChallenge");
  setTabLabel("tabSettings", "settings");
  setTabLabel("tabLogic", "logic");
  setTabLabel("tabJournal", "journal");
  renderSystemResources();
  setText("learnTitle", t.learnTitle);
  setText("learnSub", t.learnSub);
  setText("learnLogic", t.learnLogic);
  setText("learnLock", t.learnLock);
  setText("learnCompare", t.learnCompare);
  setText("learnHistory", t.learnHistory);
  setText("learnRisk", t.learnRisk);
  setText("logicLearnTitle", t.logicLearnTitle);
  setText("logicLearnSub", t.logicLearnSub);
  setText("logicMapSave", t.logicMapSave);
  setText("logicMapCompare", t.logicMapCompare);
  setText("logicMapMemo", t.logicMapMemo);
  setText("apiStatusTitle", t.apiStatus);
  setText("kisStatusLabel", t.kis);
  setText("kisModeLabel", t.kisMode);
  setText("dartStatusLabel", t.dart);
  setText("tossStatusLabel", t.toss);
  setText("ecosStatusLabel", t.ecos);
  setText("fredStatusLabel", t.fred);
  setText("liveTradingLabel", t.liveTrading);
  setText("apiStatusNote", t.apiNote);
  setText("journalApiTitle", t.apiStatus);
  setText("refreshApiStatus", t.refreshApi);
  setText("journalKisLabel", t.kis);
  setText("journalDartLabel", t.dart);
  setText("journalTossLabel", t.toss);
  setText("journalEcosLabel", t.ecos);
  setText("journalFredLabel", t.fred);
  setText("journalSafetyLabel", t.liveTrading);
  setText("macroLiveTitle", t.macroLiveTitle);
  setText("kisAccountTitle", t.kisAccountTitle);
  setText("kisLiveTitle", t.kisLiveTitle);
  setText("dartLiveTitle", t.dartLiveTitle);
  setText("dashboardLabel", t.dashboardLabel);
  setText("dashboardTitle", t.dashboardTitle);
  setText("dashboardSub", t.dashboardSub);
  setText("dashTradeJump", t.openTrading);
  setText("dashResearchJump", t.openResearch);
  setText("dashLogicJump", t.openLogic);
  setText("dashAutoLabel", t.autoPilot);
  setText("dashEquityHint", t.equityHint);
  setText("dashReturnHint", t.returnHint);
  setText("dashRiskHint", t.riskHint);
  setText("dashLogicHint", t.logicHint);
  setText("dashEquityLabel", t.equity);
  setText("dashReturnLabel", t.returnRate);
  setText("dashRiskLabel", t.risk);
  setText("dashLogicLabel", t.logicCount);
  setText("dashWatchTitle", t.watch);
  setText("dashCandidateTitle", t.candidates);
  setText("dashLogTitle", t.recentLog);
  setText("dashTopMoverLabel", t.topMover);
  setText("dashWeakMoverLabel", t.weakMover);
  setText("dashVolLeaderLabel", t.volLeader);
  setText("dashMissionTitle", t.missionTitle);
  setText("dashMissionBadge", t.missionBadge);
  setText("missionScan", t.missionScan);
  setText("missionScanSub", t.missionScanSub);
  setText("missionTest", t.missionTest);
  setText("missionTestSub", t.missionTestSub);
  setText("missionRisk", t.missionRisk);
  setText("missionRiskSub", t.missionRiskSub);
  setText("missionReview", t.missionReview);
  setText("missionReviewSub", t.missionReviewSub);
  setText("dashRiskConsoleTitle", t.riskConsole);
  setText("dashOrderUsageLabel", t.orderUsage);
  setText("dashPositionCapLabel", t.positionCap);
  ["headSymbol", "headSymbol2"].forEach((id) => setText(id, t.symbol));
  ["headPrice", "headPrice2"].forEach((id) => setText(id, t.price));
  ["headChange", "headChange2"].forEach((id) => setText(id, t.change));
  setText("watchTitle", t.watch);
  setText("refreshStatus", "\uc0c8\ub85c\uace0\uce68");
  setText("selectedLabel", t.selected);
  setText("legendPrice", "가격");
  setText("legendEquity", "MA12");
  setText("legendMa", "MA32");
  setText("bookTitle", t.orderbook);
  setText("paperTitle", t.paper);
  setText("quantityLabel", t.quantity);
  setText("buyButton", "테스트 매수");
  setText("sellButton", "테스트 매도");
  setText("autoButton", "AI 전략훈련");
  setText("cashLabel", t.cash);
  setText("marketValueLabel", t.marketValue);
  setText("researchTitle", t.strategyLab);
  setText("researchState", t.waiting);
  setText("symbolLabel", t.symbol);
  setText("symbolSearchLabel", t.symbolSearch);
  setText("strategyPresetLabel", t.strategyPresetLabel);
  setText("startDateLabel", t.startDate);
  setText("endDateLabel", t.endDate);
  setText("fastLabel", t.fast);
  setText("slowLabel", t.slow);
  setText("researchButton", t.runResearch);
  setText("runBacktest", t.runBacktest);
  setText("runMultiBacktest", t.runMultiBacktest);
  setText("strategyChartTitle", t.strategyChart);
  setText("multiCompareTitle", t.multiCompare);
  setText("transcriptStrategyTitle", t.transcriptStrategy);
  setText("runTranscriptStrategy", t.runTranscriptStrategy);
  setText("finalEquityLabel", t.finalEquity);
  setText("totalReturnLabel", t.totalReturn);
  setText("maxDrawdownLabel", t.maxDrawdown);
  setText("tradeCountLabel", t.trades);
  setText("candidateTitle", t.candidateList);
  setText("liveResearchTitle", t.liveResearch);
  setText("liveResearchButton", t.runLiveResearch);
  setText("aiTraderLabel", t.aiTraderLabel);
  setText("aiTraderTitle", t.aiTraderTitle);
  setText("refreshAiBrief", t.refreshAiBrief);
  setText("sendTelegramBrief", t.sendTelegramBrief);
  setText("aiKrTitle", t.aiKrTitle);
  setText("aiUsTitle", t.aiUsTitle);
  setText("telegramTitle", t.telegramTitle);
  setText("economicSignalTitle", t.economicSignalTitle);
  setText("hedgeStrategyTitle", t.hedgeStrategyTitle);
  setText("logicTitle", t.logicManage);
  setText("saveLogicButton", t.saveLogic);
  setText("compareButton", t.compareLogic);
  setText("compareTitle", t.compareResult);
  setText("eventLogTitle", t.eventLog);
  setText("clearLog", t.clear);
  setText("riskTitle", t.riskStatus);
  setText("riskOrdersLabel", t.orderLimit);
  setText("riskPositionLabel", t.positionLimit);
  setText("engineCountLabel", t.sourceCount);
  el("#logicName").value = "\ub098\uc758\uc804\ub7b5";
  el("#logicMemo").value = "\uba54\ubaa8";
}

function switchPage(pageId) {
  clearInstantNavigationRunState();
  document.querySelectorAll(".page").forEach((page) => page.classList.toggle("active", page.id === pageId));
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.page === pageId));
  document.querySelectorAll(".workspace-map-grid button").forEach((button) => button.classList.toggle("active", button.dataset.pageJump === pageId));
  const guide = pageGuide[pageId] || pageGuide.dashboard;
  setText("workspaceMapActive", `${guide.title}: ${guide.desc}`);
  renderPageActionGuide(pageId);
  window.CodexStockSubpages?.activate(pageId);
  if (pageId === "recommendations") hydrateRecommendationPage(false);
  if (pageId === "capitalChallenge") {
    loadCapitalChallenge(false);
    loadHundredBillionLabStatus();
    loadAiTournament(false);
  }
}

function hydrateRecommendationPage(force = false) {
  if (!force && state.recommendationPageHydrated) return;
  state.recommendationPageHydrated = true;
  loadScreener(force).catch((error) => addLog(`추천 종목 후보 갱신 실패: ${error.message}`));
  loadOpportunities(force).catch((error) => addLog(`섹터 추천 카드 갱신 실패: ${error.message}`));
  loadRadar(force).catch((error) => addLog(`추천 종목 레이더 갱신 실패: ${error.message}`));
  loadSectorNews(force).catch((error) => addLog(`섹터뉴스 갱신 실패: ${error.message}`));
}

function makeFallbackDates(count) {
  const rows = [];
  const cursor = new Date();
  while (rows.length < count) {
    const day = cursor.getDay();
    if (day !== 0 && day !== 6) rows.unshift(cursor.toLocaleDateString("sv-SE"));
    cursor.setDate(cursor.getDate() - 1);
  }
  return rows;
}

function seedQuotes() {
  symbols.forEach((symbol, index) => {
    const base = 80 + index * 18;
    const meta = symbolMeta(symbol);
    state.quotes.set(symbol, { symbol, open: base, last: base, volume: 0, name: meta.name, market: meta.market });
    state.history.set(symbol, Array.from({ length: 120 }, () => base));
    state.historyDates.set(symbol, makeFallbackDates(120));
    state.historySource.set(symbol, "초기 대기 데이터");
  });
}

function syncSymbols(nextSymbols = []) {
  const unique = [];
  nextSymbols.forEach((symbol) => {
    const normalized = normalizeSymbol(symbol);
    if (normalized && !unique.includes(normalized)) unique.push(normalized);
  });
  if (!unique.length) return;
  symbols.splice(0, symbols.length, ...unique.slice(0, 18));
  seedQuotes();
  buildWatchRows("#watchRows");
  buildWatchRows("#watchRowsTrading");
  buildTicker();
}

function buildWatchRows(targetId) {
  const key = String(targetId).replace(/^#/, "");
  const node = el(targetId);
  if (!node) return;
  node.innerHTML = symbols.map((symbol) => {
    const meta = symbolMeta(symbol);
    return `
    <div class="row watch-row" data-symbol="${symbol}">
      <span class="watch-symbol"><strong>${escapeHtml(meta.name)}</strong><small>${escapeHtml(symbolSubLabel(meta))}</small></span>
      <span data-price="${key}-${symbol}">0.00</span>
      <span data-change="${key}-${symbol}" class="flat">+0.00%</span>
      <button class="watch-remove" data-watch-remove="${symbol}" title="관심종목 제거">×</button>
    </div>
  `;
  }).join("");
}

function buildTicker() {
  el("#tickerStrip").innerHTML = symbols.slice(0, 8).map((symbol) => {
    const meta = symbolMeta(symbol);
    return `
    <span class="ticker-item"><strong title="${escapeHtml(meta.name)}">${escapeHtml(meta.name)}</strong><small>${escapeHtml(symbolSubLabel(meta))}</small><span data-ticker="${symbol}" class="flat">0.00 +0.00%</span></span>
  `;
  }).join("");
}

function quoteClass(changePct) {
  if (changePct > 0.02) return "up";
  if (changePct < -0.02) return "down";
  return "flat";
}

function updateClock() {
  setText("clock", new Date().toLocaleTimeString());
}

async function tickMarket(fast = false) {
  if (state.marketBusy) return;
  state.marketBusy = true;
  try {
    const requestSymbols = fast ? [state.active] : symbols;
    const params = new URLSearchParams({ symbol: state.active, bars: "360", symbols: requestSymbols.join(",") });
    const response = await fetch(`/api/market?${params.toString()}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "시장 데이터 조회 실패");
    (result.quotes || []).forEach((quote) => {
      const open = Number(quote.previous_close || quote.open || quote.price || 0);
      const meta = symbolMeta(quote.symbol, quote);
      state.quotes.set(quote.symbol, {
        symbol: quote.symbol,
        open: open || Number(quote.price || 0),
        last: Number(quote.price || 0),
        volume: Number(quote.volume || 0),
        source: quote.source || result.source || "-",
        name: meta.name,
        market: quote.market || meta.market,
      });
    });
    state.history.set(state.active, result.history || []);
    state.historyDates.set(state.active, Array.isArray(result.history_dates) && result.history_dates.length ? result.history_dates : makeFallbackDates((result.history || []).length));
    state.historySource.set(state.active, result.history_source || result.source || "데이터");
    state.minuteRows.set(state.active, Array.isArray(result.minute_rows) ? result.minute_rows : []);
    state.minuteSource.set(state.active, result.minute_source || "");
    state.minuteMomentum.set(state.active, Number(result.minute_momentum_pct || 0));
    syncPriceChartWindowOnDataChange(state.active);
    state.orderbook = result.orderbook;
    renderMarket();
    await loadPortfolio();
    setText("watchlistMeta", `${symbols.length}개 관심종목 · ${fast ? "선택종목 우선조회" : "전체 갱신"} · ${result.message || result.source || "실제 우선"} · ${result.generated_at || ""}`);
  } catch (error) {
    addLog(`시장 데이터 조회 실패: ${error.message}`);
  } finally {
    state.marketBusy = false;
  }
}

function renderMarket() {
  const marketRows = [];
  symbols.forEach((symbol) => {
    const quote = state.quotes.get(symbol);
    if (!quote) return;
    const open = Number(quote.open || quote.last || 0);
    const last = Number(quote.last || 0);
    const change = open ? ((last / open) - 1) * 100 : 0;
    marketRows.push({ symbol, name: symbolDisplayName(symbol, quote), price: last, change, volume: quote.volume || 0 });
    const klass = quoteClass(change);
    document.querySelectorAll(`[data-symbol="${symbol}"]`).forEach((row) => row.classList.toggle("active", symbol === state.active));
    ["watchRows", "watchRowsTrading"].forEach((targetId) => {
      const priceNode = document.querySelector(`[data-price="${targetId}-${symbol}"]`);
      const changeNode = document.querySelector(`[data-change="${targetId}-${symbol}"]`);
      if (priceNode) priceNode.textContent = money(last);
      if (changeNode) {
        changeNode.textContent = pct(change);
        changeNode.className = klass;
      }
    });
    const tickerNode = document.querySelector(`[data-ticker="${symbol}"]`);
    if (tickerNode) {
      tickerNode.textContent = `${money(last)} ${pct(change)}`;
      tickerNode.className = klass;
    }
  });
  renderActiveQuote();
  renderDashboardMarket(marketRows);
  drawChart();
  renderOrderBook();
  renderMinuteFlow();
}

function renderDashboardMarket(rows) {
  if (!rows.length) return;
  const sorted = [...rows].sort((a, b) => b.change - a.change);
  const top = sorted[0];
  const weak = sorted[sorted.length - 1];
  const volume = [...rows].sort((a, b) => b.volume - a.volume)[0];
  const up = rows.filter((row) => row.change >= 0).length;
  const down = rows.length - up;
  setText("dashMarketBreadth", t.marketBreadth.replace("{up}", up).replace("{down}", down));
  setText("dashTopMover", `${symbolDisplayName(top.symbol, top)} ${pct(top.change)}`);
  setText("dashWeakMover", `${symbolDisplayName(weak.symbol, weak)} ${pct(weak.change)}`);
  setText("dashVolLeader", volume.name || symbolDisplayName(volume.symbol));
  el("#dashTopMover").className = quoteClass(top.change);
  el("#dashWeakMover").className = quoteClass(weak.change);
  setText("dashActiveSymbol", symbolDisplayName(state.active));
  const active = rows.find((row) => row.symbol === state.active) || rows[0];
  const signal = active.change > 0.4 ? t.buy : active.change < -0.4 ? t.sell : t.hold;
  setText("dashActiveSignal", signal);
  el("#dashActiveSignal").className = quoteClass(active.change);
  setText("dashDecision", `${symbolDisplayName(state.active)}: ${t.decisionReady}`);
  setText("dashAutoState", t.normal);
}

function renderActiveQuote() {
  const quote = state.quotes.get(state.active);
  if (!quote) return;
  const open = Number(quote.open || quote.last || 0);
  const last = Number(quote.last || 0);
  const change = open ? ((last / open) - 1) * 100 : 0;
  const meta = symbolMeta(state.active, quote);
  setText("selectedLabel", `${t.selected} · ${meta.name} · ${symbolSubLabel(meta)}`);
  setText("activeSymbol", meta.name);
  setText("activePrice", money(last));
  setText("activeChange", pct(change));
  el("#activeChange").className = quoteClass(change);
  el("#symbol").value = state.active;
  renderOrderPreview();
}

function renderOrderPreview() {
  const quote = state.quotes.get(state.active) || {};
  const meta = symbolMeta(state.active, quote);
  const price = Number(quote.last || 0);
  const quantity = Math.max(0, Number(el("#quantity")?.value || 0));
  setText("orderPreviewSymbol", meta.name);
  setText("orderPreviewPrice", price ? money(price) : "-");
  setText("orderPreviewNotional", price && quantity ? money(price * quantity) : "-");
  setText("orderPreviewMode", "AI 훈련/감독");
}

function renderOrderBook() {
  const quote = state.quotes.get(state.active);
  if (!quote) return;
  const last = Number(quote.last || 0);
  const spread = state.orderbook ? state.orderbook.spread : Math.max(0.01, last * 0.00035);
  const asks = state.orderbook ? state.orderbook.asks : [];
  const bids = state.orderbook ? state.orderbook.bids : [];
  const maxSize = Math.max(...asks.map((row) => row.size), ...bids.map((row) => row.size), 1);
  el("#askRows").innerHTML = asks.map((row) => bookRow(row, maxSize, "ASK")).join("");
  el("#bidRows").innerHTML = bids.map((row) => bookRow(row, maxSize, "BID")).join("");
  setText("midPrice", money(last));
  setText("spread", `${t.spread} ${Number(spread).toFixed(3)}`);
}

function bookRow(row, maxSize, side) {
  const depth = Math.max(10, (row.size / maxSize) * 100);
  return `<div class="book-row" style="--depth:${depth}%"><span class="${side === "ASK" ? "up" : "down"}">${side === "ASK" ? t.sell : t.buy}</span><span>${money(row.price)}</span><span>${row.size}</span></div>`;
}

function renderMinuteFlow() {
  const rows = state.minuteRows.get(state.active) || [];
  const source = state.minuteSource.get(state.active) || "";
  const momentum = Number(state.minuteMomentum.get(state.active) || 0);
  const box = el("#minuteFlowRows");
  if (!box) return;
  if (!rows.length) {
    setText("minuteFlowState", "분봉 데이터 대기");
    box.innerHTML = `<div class="minute-flow-empty">한투 분봉을 불러오는 중입니다.</div>`;
    return;
  }
  const recent = rows.slice(-10);
  const prices = recent.map((row) => Number(row.close || 0)).filter((value) => value > 0);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = Math.max(1, max - min);
  const latest = recent[recent.length - 1] || {};
  const klass = momentum > 0.2 ? "up" : momentum < -0.2 ? "down" : "flat";
  setText("minuteFlowState", `최근 ${rows.length}개 · ${pct(momentum)} · ${latest.time || "-"} · ${source || "-"}`);
  box.innerHTML = recent.map((row, index) => {
    const close = Number(row.close || 0);
    const previous = index > 0 ? Number(recent[index - 1].close || close) : close;
    const move = close - previous;
    const height = 18 + ((close - min) / range) * 58;
    const rowClass = move > 0 ? "up" : move < 0 ? "down" : "flat";
    return `
      <div class="minute-flow-bar ${rowClass}" title="${escapeHtml(row.time || "-")} ${money(close)}">
        <span style="height:${height}%"></span>
        <small>${escapeHtml(String(row.time || "").slice(0, 5))}</small>
      </div>`;
  }).join("") + `<div class="minute-flow-summary ${klass}"><b>${pct(momentum)}</b><small>${money(Number(latest.close || 0))}</small></div>`;
}

function renderIntradayMinuteRadar(payload = {}) {
  const box = el("#intradayMinuteRadarRows");
  if (!box) return;
  state.intradayMinuteRadar = payload;
  const rows = Array.isArray(payload.items) ? payload.items : [];
  const generated = payload.generated_at ? formatDateTimeShort(payload.generated_at) : "조회 대기";
  const recordedLabel = payload.recorded ? " · 기록됨" : "";
  setText("intradayMinuteRadarState", payload.ok === false ? "조회 실패" : rows.length ? `${rows.length}개 · ${generated}${recordedLabel}` : "여러 종목 수급 대기");
  if (!rows.length) {
    box.innerHTML = `<div class="minute-flow-empty">${escapeHtml(payload.ok === false ? payload.message || "분봉 레이더 조회에 실패했습니다." : "분봉 레이더 갱신을 누르면 관심종목과 AI 후보를 비교합니다.")}</div>`;
    return;
  }
  box.innerHTML = rows.slice(0, 8).map((row, index) => {
    const stateClass = row.state === "strong" ? "up" : row.state === "weak" ? "down" : row.state === "missing" ? "missing" : "flat";
    const name = row.name || symbolDisplayName(row.symbol || "");
    return `
      <article class="${stateClass}">
        <b>${index + 1}</b>
        <strong>${escapeHtml(name)}</strong>
        <span>${escapeHtml(row.action || "대기")} · 점수 ${Number(row.score || 0).toFixed(1)}</span>
        <small>분봉 ${pct(row.minute_momentum_pct || 0)} · 체결강도 ${Number(row.avg_strength || 0).toFixed(1)} · 매수압력 ${Number(row.buy_pressure || 0).toFixed(1)}</small>
        <em>${escapeHtml(row.reason || "-")} · ${escapeHtml(row.latest_minute_time || row.latest_conclusion_time || "-")}</em>
      </article>
    `;
  }).join("");
}

async function loadIntradayMinuteRadar(silent = true) {
  try {
    const radarSymbols = Array.from(new Set([state.active, ...symbols])).filter((symbol) => /^\d{6}$/.test(String(symbol || ""))).slice(0, 8);
    const params = new URLSearchParams({ symbols: radarSymbols.join(","), limit: "8" });
    const response = await fetch(`/api/market/intraday-minute-radar?${params.toString()}`);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.error || result.message || "분봉 레이더 조회 실패");
    renderIntradayMinuteRadar(result);
    if (!silent) {
      const top = result.top || {};
      addLog(`분봉 레이더: ${top.name || symbolDisplayName(top.symbol || "") || "-"} ${top.action || "-"} · 점수 ${Number(top.score || 0).toFixed(1)} · 읽기전용`);
    }
    return result;
  } catch (error) {
    setText("intradayMinuteRadarState", "조회 실패");
    renderIntradayMinuteRadar({ ok: false, items: [], message: error.message });
    if (!silent) addLog(`분봉 레이더 조회 실패: ${error.message}`);
    return null;
  }
}

function renderKisRankRadar(payload = {}) {
  const box = el("#kisRankRadarRows");
  if (!box) return;
  const rows = Array.isArray(payload.items) ? payload.items : [];
  const generated = payload.generated_at ? formatDateTimeShort(payload.generated_at) : "조회 대기";
  setText("kisRankRadarState", payload.ok === false ? "조회 실패" : rows.length ? `${rows.length}개 · ${generated}` : "순위 조회 대기");
  if (!rows.length) {
    box.innerHTML = `<div class="minute-flow-empty">${escapeHtml(payload.ok === false ? payload.message || "한투 거래대금 순위 조회에 실패했습니다." : "거래대금 순위 갱신을 누르면 한투 순위분석 결과를 보여줍니다.")}</div>`;
    return;
  }
  box.innerHTML = rows.slice(0, 12).map((row, index) => {
    const stateClass = row.state === "strong" ? "up" : row.state === "down" ? "down" : row.state === "watch" ? "flat" : "missing";
    const name = row.name || symbolDisplayName(row.symbol || "");
    return `
      <article class="${stateClass} kis-rank-row">
        <b>${index + 1}</b>
        <strong>${escapeHtml(name)}</strong>
        <span>${escapeHtml(row.action || "대기")} · 점수 ${Number(row.score || 0).toFixed(1)}</span>
        <small>거래대금 ${Number(row.amount_eok || 0).toLocaleString()}억 · 등락 ${pct(row.change_pct || 0)} · 현재가 ${money(row.price || 0)}</small>
        <em>${escapeHtml(row.reason || "-")}</em>
      </article>
    `;
  }).join("");
}

async function loadKisRankRadar(silent = true) {
  try {
    const market = el("#kisRankRadarMarket")?.value || "all";
    const params = new URLSearchParams({ kind: "amount", market, limit: "20" });
    const response = await fetch(`/api/kis/rank-radar?${params.toString()}`);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.message || result.error || "한투 거래대금 순위 조회 실패");
    renderKisRankRadar(result);
    if (!silent) {
      const top = result.top || {};
      addLog(`한투 거래대금 랭킹: ${top.name || symbolDisplayName(top.symbol || "") || "-"} ${top.action || "-"} · 점수 ${Number(top.score || 0).toFixed(1)} · ${Number(top.amount_eok || 0).toLocaleString()}억`);
    }
    return result;
  } catch (error) {
    setText("kisRankRadarState", "조회 실패");
    renderKisRankRadar({ ok: false, items: [], message: error.message });
    if (!silent) addLog(`한투 거래대금 랭킹 조회 실패: ${error.message}`);
    return null;
  }
}

function renderKisFluctuationRadar(payload = {}) {
  const box = el("#kisFluctuationRadarRows");
  if (!box) return;
  const rows = Array.isArray(payload.items) ? payload.items : [];
  const generated = payload.generated_at ? formatDateTimeShort(payload.generated_at) : "조회 대기";
  const label = payload.direction === "down" ? "급락" : "급등";
  setText("kisFluctuationRadarState", payload.ok === false ? "조회 실패" : rows.length ? `${label} ${rows.length}개 · ${generated}` : "등락률 조회 대기");
  if (!rows.length) {
    box.innerHTML = `<div class="minute-flow-empty">${escapeHtml(payload.ok === false ? payload.message || "한투 등락률 순위 조회에 실패했습니다." : "등락률 순위 갱신을 누르면 급등/급락 후보를 보여줍니다.")}</div>`;
    return;
  }
  box.innerHTML = rows.slice(0, 12).map((row, index) => {
    const stateClass = row.state === "strong" ? "up" : row.state === "down" ? "down" : row.state === "watch" ? "flat" : "missing";
    const name = row.name || symbolDisplayName(row.symbol || "");
    const liquidity = Number(row.amount_eok || 0) > 0
      ? `거래대금 ${Number(row.amount_eok || 0).toLocaleString()}억`
      : `거래량 ${Number(row.volume || 0).toLocaleString()}주`;
    return `
      <article class="${stateClass} kis-fluctuation-row">
        <b>${index + 1}</b>
        <strong>${escapeHtml(name)}</strong>
        <span>${escapeHtml(row.action || "대기")} · 점수 ${Number(row.score || 0).toFixed(1)}</span>
        <small>등락 ${pct(row.change_pct || 0)} · ${escapeHtml(liquidity)} · 현재가 ${money(row.price || 0)}</small>
        <em>${escapeHtml(row.reason || "-")}</em>
      </article>
    `;
  }).join("");
}

async function loadKisFluctuationRadar(silent = true) {
  try {
    const market = el("#kisFluctuationMarket")?.value || "all";
    const direction = el("#kisFluctuationDirection")?.value || "up";
    const params = new URLSearchParams({ direction, market, limit: "20" });
    const response = await fetch(`/api/kis/fluctuation-radar?${params.toString()}`);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.message || result.error || "한투 등락률 순위 조회 실패");
    renderKisFluctuationRadar(result);
    if (!silent) {
      const top = result.top || {};
      const label = result.direction === "down" ? "급락" : "급등";
      addLog(`한투 ${label} 랭킹: ${top.name || symbolDisplayName(top.symbol || "") || "-"} ${top.action || "-"} · 등락 ${pct(top.change_pct || 0)} · 점수 ${Number(top.score || 0).toFixed(1)}`);
    }
    return result;
  } catch (error) {
    setText("kisFluctuationRadarState", "조회 실패");
    renderKisFluctuationRadar({ ok: false, items: [], message: error.message });
    if (!silent) addLog(`한투 등락률 랭킹 조회 실패: ${error.message}`);
    return null;
  }
}

function renderKisVolumePowerRadar(payload = {}) {
  const box = el("#kisVolumePowerRadarRows");
  if (!box) return;
  const rows = Array.isArray(payload.items) ? payload.items : [];
  const generated = payload.generated_at ? formatDateTimeShort(payload.generated_at) : "조회 대기";
  setText("kisVolumePowerRadarState", payload.ok === false ? "조회 실패" : rows.length ? `${rows.length}개 · ${generated}` : "체결강도 조회 대기");
  if (!rows.length) {
    box.innerHTML = `<div class="minute-flow-empty">${escapeHtml(payload.ok === false ? payload.message || "한투 체결강도 상위 조회에 실패했습니다." : "체결강도 순위 갱신을 누르면 매수 체결 우위 후보를 보여줍니다.")}</div>`;
    return;
  }
  box.innerHTML = rows.slice(0, 12).map((row, index) => {
    const stateClass = row.state === "strong" ? "up" : row.state === "down" ? "down" : row.state === "watch" ? "flat" : "missing";
    const name = row.name || symbolDisplayName(row.symbol || "");
    const power = Number(row.power || 0);
    const liquidity = Number(row.amount_eok || 0) > 0
      ? `거래대금 ${Number(row.amount_eok || 0).toLocaleString()}억`
      : `거래량 ${Number(row.volume || 0).toLocaleString()}주`;
    return `
      <article class="${stateClass} kis-volume-power-row">
        <b>${index + 1}</b>
        <strong>${escapeHtml(name)}</strong>
        <span>${escapeHtml(row.action || "대기")} · 점수 ${Number(row.score || 0).toFixed(1)}</span>
        <small>체결강도 ${power.toFixed(1)} · 등락 ${pct(row.change_pct || 0)} · ${escapeHtml(liquidity)}</small>
        <em>${escapeHtml(row.reason || "-")}</em>
      </article>
    `;
  }).join("");
}

async function loadKisVolumePowerRadar(silent = true) {
  try {
    const market = el("#kisVolumePowerMarket")?.value || "all";
    const params = new URLSearchParams({ market, limit: "20" });
    const response = await fetch(`/api/kis/volume-power-radar?${params.toString()}`);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.message || result.error || "한투 체결강도 상위 조회 실패");
    renderKisVolumePowerRadar(result);
    if (!silent) {
      const top = result.top || {};
      addLog(`한투 체결강도 랭킹: ${top.name || symbolDisplayName(top.symbol || "") || "-"} ${top.action || "-"} · 체결강도 ${Number(top.power || 0).toFixed(1)} · 점수 ${Number(top.score || 0).toFixed(1)}`);
    }
    return result;
  } catch (error) {
    setText("kisVolumePowerRadarState", "조회 실패");
    renderKisVolumePowerRadar({ ok: false, items: [], message: error.message });
    if (!silent) addLog(`한투 체결강도 랭킹 조회 실패: ${error.message}`);
    return null;
  }
}

function renderKisQuoteBalanceRadar(payload = {}) {
  const box = el("#kisQuoteBalanceRadarRows");
  if (!box) return;
  const rows = Array.isArray(payload.items) ? payload.items : [];
  const generated = payload.generated_at ? formatDateTimeShort(payload.generated_at) : "조회 대기";
  const label = payload.kind === "sell" ? "매도잔량" : "매수잔량";
  setText("kisQuoteBalanceRadarState", payload.ok === false ? "조회 실패" : rows.length ? `${label} ${rows.length}개 · ${generated}` : "호가잔량 조회 대기");
  if (!rows.length) {
    box.innerHTML = `<div class="minute-flow-empty">${escapeHtml(payload.ok === false ? payload.message || "한투 호가잔량 순위 조회에 실패했습니다." : "호가잔량 순위 갱신을 누르면 매수벽/매도벽 후보를 보여줍니다.")}</div>`;
    return;
  }
  box.innerHTML = rows.slice(0, 12).map((row, index) => {
    const stateClass = row.state === "strong" ? "up" : row.state === "down" ? "down" : row.state === "watch" ? "flat" : "missing";
    const name = row.name || symbolDisplayName(row.symbol || "");
    const net = Number(row.net_buy_balance || 0);
    const netLabel = net >= 0 ? `순매수잔량 ${net.toLocaleString()}주` : `순매도잔량 ${Math.abs(net).toLocaleString()}주`;
    return `
      <article class="${stateClass} kis-quote-balance-row">
        <b>${index + 1}</b>
        <strong>${escapeHtml(name)}</strong>
        <span>${escapeHtml(row.action || "대기")} · 점수 ${Number(row.score || 0).toFixed(1)}</span>
        <small>매수 ${Number(row.buy_rate || 0).toFixed(1)}% · 매도 ${Number(row.sell_rate || 0).toFixed(1)}% · ${escapeHtml(netLabel)}</small>
        <em>${escapeHtml(row.reason || "-")}</em>
      </article>
    `;
  }).join("");
}

async function loadKisQuoteBalanceRadar(silent = true) {
  try {
    const market = el("#kisQuoteBalanceMarket")?.value || "all";
    const kind = el("#kisQuoteBalanceKind")?.value || "buy";
    const params = new URLSearchParams({ kind, market, limit: "20" });
    const response = await fetch(`/api/kis/quote-balance-radar?${params.toString()}`);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.message || result.error || "한투 호가잔량 순위 조회 실패");
    renderKisQuoteBalanceRadar(result);
    if (!silent) {
      const top = result.top || {};
      const label = result.kind === "sell" ? "매도잔량" : "매수잔량";
      addLog(`한투 ${label} 랭킹: ${top.name || symbolDisplayName(top.symbol || "") || "-"} ${top.action || "-"} · 매수 ${Number(top.buy_rate || 0).toFixed(1)}% · 매도 ${Number(top.sell_rate || 0).toFixed(1)}%`);
    }
    return result;
  } catch (error) {
    setText("kisQuoteBalanceRadarState", "조회 실패");
    renderKisQuoteBalanceRadar({ ok: false, items: [], message: error.message });
    if (!silent) addLog(`한투 호가잔량 랭킹 조회 실패: ${error.message}`);
    return null;
  }
}

const conditionPresetValues = {
  active_buy: { minAmount: 3, minChange: -2, maxChange: 18, minPower: 115, minBuyRate: 0, maxSellRate: 95, minScore: 42 },
  breakout: { minAmount: 8, minChange: 1, maxChange: 24, minPower: 125, minBuyRate: 0, maxSellRate: 88, minScore: 48 },
  support: { minAmount: 3, minChange: -4, maxChange: 12, minPower: 95, minBuyRate: 60, maxSellRate: 75, minScore: 48 },
  risk: { minAmount: 3, minChange: -30, maxChange: 30, minPower: 0, minBuyRate: 0, maxSellRate: 100, minScore: 35 },
};

function setConditionInputValue(id, value) {
  const node = el(id);
  if (node) node.value = String(value);
}

function applyConditionPresetValues(preset = el("#conditionPreset")?.value || "active_buy") {
  const values = conditionPresetValues[preset];
  if (!values) return;
  setConditionInputValue("#conditionMinAmount", values.minAmount);
  setConditionInputValue("#conditionMinChange", values.minChange);
  setConditionInputValue("#conditionMaxChange", values.maxChange);
  setConditionInputValue("#conditionMinPower", values.minPower);
  setConditionInputValue("#conditionMinBuyRate", values.minBuyRate);
  setConditionInputValue("#conditionMaxSellRate", values.maxSellRate);
  setConditionInputValue("#conditionMinScore", values.minScore);
}

function readConditionNumber(id, fallback) {
  const value = Number(el(id)?.value);
  return Number.isFinite(value) ? value : fallback;
}

function conditionScreenerParams() {
  const preset = el("#conditionPreset")?.value || "active_buy";
  return new URLSearchParams({
    preset,
    market: el("#conditionMarket")?.value || "all",
    min_amount_eok: String(readConditionNumber("#conditionMinAmount", 3)),
    min_change_pct: String(readConditionNumber("#conditionMinChange", -3)),
    max_change_pct: String(readConditionNumber("#conditionMaxChange", 30)),
    min_power: String(readConditionNumber("#conditionMinPower", 110)),
    min_buy_rate: String(readConditionNumber("#conditionMinBuyRate", 50)),
    max_sell_rate: String(readConditionNumber("#conditionMaxSellRate", 85)),
    min_score: String(readConditionNumber("#conditionMinScore", 45)),
    limit: "20",
  });
}

function renderConditionScreener(payload = {}) {
  const box = el("#conditionScreenerRows");
  if (!box) return;
  state.lastConditionScreener = payload;
  const rows = Array.isArray(payload.items) ? payload.items : [];
  const generated = payload.generated_at ? formatDateTimeShort(payload.generated_at) : "조회 대기";
  const label = payload.conditions?.preset_label || "조건검색";
  setText("conditionScreenerState", payload.ok === false ? "조회 실패" : rows.length ? `${label} ${rows.length}개 · ${generated}` : "조건 통과 없음");
  if (!rows.length) {
    box.innerHTML = `<div class="minute-flow-empty">${escapeHtml(payload.message || "조건검색 실행을 누르면 조건에 맞는 종목만 표시합니다.")}</div>`;
    return;
  }
  box.innerHTML = rows.slice(0, 12).map((row, index) => {
    const stateClass = row.state === "strong" ? "up" : row.state === "down" ? "down" : row.state === "watch" ? "flat" : "missing";
    const name = row.name || symbolDisplayName(row.symbol || "");
    const tags = Array.isArray(row.tags) ? row.tags.slice(0, 5).join(" · ") : "";
    return `
      <article class="${stateClass} condition-screener-row">
        <b>${index + 1}</b>
        <strong>${escapeHtml(name)}</strong>
        <span>${escapeHtml(row.action || "조건 통과")} · 종합 ${Number(row.score || 0).toFixed(1)}</span>
        <small>거래대금 ${Number(row.amount_eok || 0).toLocaleString()}억 · 등락 ${pct(row.change_pct || 0)} · 체결강도 ${Number(row.power || 0).toFixed(1)} · 매수잔량 ${Number(row.buy_rate || 0).toFixed(1)}%</small>
        <em>${escapeHtml(row.reason || "-")}${tags ? ` · ${escapeHtml(tags)}` : ""}</em>
        <button type="button" data-condition-symbol="${escapeHtml(row.symbol || "")}">차트로 보기</button>
      </article>
    `;
  }).join("");
}

function renderConditionScreenerHistory(payload = {}) {
  const box = el("#conditionScreenerHistoryRows");
  if (!box) return;
  state.lastConditionScreenerHistory = payload;
  const rows = Array.isArray(payload.items) ? payload.items : [];
  if (!rows.length) {
    box.innerHTML = `<div class="minute-flow-empty">${escapeHtml(payload.message || "아직 저장된 조건검색 기록이 없습니다.")}</div>`;
    return;
  }
  box.innerHTML = rows.slice(0, 8).map((row) => {
    const top = row.top || {};
    const conditions = row.conditions || {};
    const topName = top.name || symbolDisplayName(top.symbol || "") || "조건 통과 없음";
    const items = Array.isArray(row.items) ? row.items : [];
    const itemNames = items.slice(0, 4).map((item) => item.name || symbolDisplayName(item.symbol || "")).filter(Boolean).join(" · ");
    return `
      <article class="condition-screener-history-row">
        <strong>${escapeHtml(topName)}</strong>
        <span>${escapeHtml(conditions.preset_label || "직접 조건")} · ${formatDateTimeShort(row.created_at || "")}</span>
        <small>${Number(row.count || 0)}개 통과 / ${Number(row.raw_count || 0)}개 후보 · 1순위 ${Number(top.score || 0).toFixed(1)}점 · 거래대금 ${Number(top.amount_eok || 0).toLocaleString()}억</small>
        <em>${escapeHtml(itemNames || row.message || "반복 검색 기록을 쌓는 중입니다.")}</em>
      </article>
    `;
  }).join("");
}

async function loadConditionScreener(silent = true) {
  try {
    setText("conditionScreenerState", "검색 중");
    const response = await fetch(`/api/kis/condition-screener?${conditionScreenerParams().toString()}`);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.message || result.error || "조건검색 실패");
    renderConditionScreener(result);
    loadConditionScreenerHistory(true).catch((error) => addLog(`조건검색 기록 조회 실패: ${error.message}`));
    loadLiveDecisionContext(true).catch((error) => addLog(`AI 통합 판단 갱신 실패: ${error.message}`));
    if (!silent) {
      const top = result.top || {};
      addLog(`조건검색: ${top.name || symbolDisplayName(top.symbol || "") || "조건 통과 없음"} · ${top.action || result.message || "-"} · ${Number(top.score || 0).toFixed(1)}점`);
    }
    return result;
  } catch (error) {
    setText("conditionScreenerState", "조회 실패");
    renderConditionScreener({ ok: false, items: [], message: error.message });
    if (!silent) addLog(`조건검색 실패: ${error.message}`);
    return null;
  }
}

async function loadConditionScreenerHistory(silent = true) {
  try {
    const response = await fetch("/api/kis/condition-screener/history?limit=8");
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.message || result.error || "조건검색 기록 조회 실패");
    renderConditionScreenerHistory(result);
    if (!silent) addLog(`조건검색 기록 새로고침: ${Number(result.count || 0)}건`);
    return result;
  } catch (error) {
    renderConditionScreenerHistory({ ok: false, items: [], message: error.message });
    if (!silent) addLog(`조건검색 기록 조회 실패: ${error.message}`);
    return null;
  }
}

function renderLiveDecisionContext(payload = {}) {
  const box = el("#liveDecisionContextRows");
  if (!box) return;
  state.lastLiveDecisionContext = payload;
  const rows = Array.isArray(payload.candidates) ? payload.candidates : [];
  const context = payload.context || {};
  const trainingMemory = context.training_memory || {};
  const trainingTopStaff = trainingMemory.top_staff || {};
  const generated = payload.generated_at ? formatDateTimeShort(payload.generated_at) : "조회 대기";
  const refreshLabel = payload.refresh ? "실데이터 재검증" : "최근 기록 묶음";
  setText("liveDecisionContextState", payload.ok === false ? "조회 실패" : rows.length ? `${refreshLabel} ${rows.length}개 · ${generated}` : "통합 판단 후보 없음");
  if (!rows.length) {
    box.innerHTML = `
      <div class="live-decision-context-empty">
        <strong>${escapeHtml(payload.headline || "아직 통합 판단 후보가 없습니다.")}</strong>
        <span>${escapeHtml(payload.message || payload.safety || "조건검색이나 분봉 레이더를 먼저 갱신하면 후보가 표시됩니다.")}</span>
      </div>
    `;
    return;
  }
  const missingLinks = Array.isArray(payload.missing_links) ? payload.missing_links : [];
  const nextActions = Array.isArray(payload.next_actions) ? payload.next_actions : [];
  const contextChips = [
    `사전점검 ${Number(context.preflight_score || 0).toFixed(1)}점`,
    `차단 ${Number(context.block_count || 0)}개`,
    `대기 ${Number(context.wait_count || 0)}개`,
    context.execution_freshness ? `체결감지 ${context.execution_freshness}` : "",
    trainingMemory.record_count ? `왕중왕전 ${Number(trainingMemory.record_count || 0).toLocaleString()}건` : "",
    trainingMemory.learning_event_count ? `학습사건 ${Number(trainingMemory.learning_event_count || 0).toLocaleString()}건` : "",
    trainingTopStaff.display_name ? `우선직원 ${trainingTopStaff.display_name}` : "",
    context.order_quota || "",
  ].filter(Boolean);
  box.innerHTML = `
    <div class="live-decision-context-summary">
      <div>
        <strong>${escapeHtml(payload.headline || "AI 통합 판단")}</strong>
        <span>${contextChips.map((item) => `<b>${escapeHtml(item)}</b>`).join("")}</span>
      </div>
      <small>${escapeHtml(payload.safety || "읽기전용 판단입니다. 실제 주문은 실행하지 않습니다.")}</small>
    </div>
    <div class="live-decision-candidate-grid">
      ${rows.slice(0, 8).map((row, index) => {
        const metrics = row.metrics || {};
        const why = Array.isArray(row.why) ? row.why : [];
        const missing = Array.isArray(row.missing) ? row.missing : [];
        const sources = Array.isArray(row.sources) ? row.sources : [];
        const memory = row.training_memory || {};
        const evidenceCount = Array.isArray(memory.evidence) ? memory.evidence.length : 0;
        const memoryLineRaw = memory.ok
          ? `학습기억: ${memory.regime_hint || "-"} · ${memory.matched_staff || "-"} · 추가검증 ${evidenceCount}건 · 보너스 ${Number(memory.score_bonus || 0).toFixed(1)}점`
          : "훈련기억: 매칭 대기";
        const memoryLine = row.learning_summary || memoryLineRaw;
        const tone = row.tone === "strong" ? "up" : row.tone === "weak" ? "down" : row.tone === "wait" ? "wait" : "flat";
        return `
          <article class="${tone}">
            <div class="live-decision-rank">${index + 1}</div>
            <div class="live-decision-main">
              <strong>${escapeHtml(row.name || symbolDisplayName(row.symbol || ""))}</strong>
              <span>${escapeHtml(row.decision || "대기")} · 통합 ${Number(row.score || 0).toFixed(1)}점</span>
              <small>등락 ${pct(metrics.change_pct || 0)} · 거래대금 ${Number(metrics.amount_eok || 0).toLocaleString()}억 · 체결강도 ${Number(metrics.power || 0).toFixed(1)} · 분봉 ${pct(metrics.minute_momentum_pct || 0)}</small>
              <small class="live-decision-memory">${escapeHtml(memoryLine)}</small>
            </div>
            <div class="live-decision-reason">
              <b>${escapeHtml(row.action || "추가 확인")}</b>
              <em>${escapeHtml(why.join(" · ") || "근거 기록 대기")}</em>
              <small>${sources.length ? `연결: ${escapeHtml(sources.join(", "))}` : "연결 신호 없음"}${missing.length ? ` · 부족: ${escapeHtml(missing.join(", "))}` : ""}</small>
            </div>
          </article>
        `;
      }).join("")}
    </div>
    ${missingLinks.length || nextActions.length ? `
      <div class="live-decision-context-notes">
        ${missingLinks.slice(0, 4).map((item) => `<span class="missing">${escapeHtml(item)}</span>`).join("")}
        ${nextActions.slice(0, 3).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
      </div>
    ` : ""}
  `;
}

async function loadLiveDecisionContext(silent = true, options = {}) {
  try {
    const params = new URLSearchParams({
      limit: String(options.limit || 8),
      refresh: options.refresh ? "1" : "0",
    });
    setText("liveDecisionContextState", options.refresh ? "실데이터 재검증 중" : "통합 판단 갱신 중");
    const response = await fetch(`/api/ai/live-decision-context?${params.toString()}`);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.message || result.error || "통합 판단 조회 실패");
    renderLiveDecisionContext(result);
    if (!silent) {
      const top = result.top || {};
      addLog(`AI 통합 판단: ${top.name || symbolDisplayName(top.symbol || "") || "후보 없음"} · ${top.decision || result.headline || "-"} · ${Number(top.score || 0).toFixed(1)}점`);
    }
    return result;
  } catch (error) {
    setText("liveDecisionContextState", "조회 실패");
    renderLiveDecisionContext({ ok: false, candidates: [], headline: "통합 판단 조회 실패", message: error.message, safety: "실제 주문은 실행하지 않았습니다." });
    if (!silent) addLog(`AI 통합 판단 조회 실패: ${error.message}`);
    return null;
  }
}

function maturityScoreClass(score) {
  const value = Number(score || 0);
  if (value >= 80) return "excellent";
  if (value >= 70) return "good";
  if (value >= 60) return "watch";
  return "weak";
}

function renderCodexstockMaturity(payload = {}) {
  state.lastMaturityScore = payload;
  const overall = Number(payload.overall_score || 0);
  const architectureScore = Number(payload.architecture_score ?? overall);
  const operationalMaturityScore = Number(payload.operational_maturity_score ?? overall);
  const performanceEvidenceScore = Number(payload.performance_evidence_score || 0);
  const delta = Number(payload.delta || 0);
  const baselineDelta = Number(payload.baseline_delta || 0);
  setText("maturityOverall", `${overall.toFixed(1)}점 / ${Number(payload.overall_10 || overall / 10).toFixed(1)}/10`);
  setText("maturityGrade", payload.grade || "-");
  setText("maturityVerdict", payload.verdict || "완성도 점수를 계산하는 중입니다.");
  setText("maturityDelta", `기준 ${baselineDelta >= 0 ? "+" : ""}${baselineDelta.toFixed(1)}점 · 직전 ${delta >= 0 ? "+" : ""}${delta.toFixed(1)}점`);
  const cacheNote = payload.cached ? ` · 빠른표시 ${Math.round(Number(payload.cache_age_seconds || 0))}초` : "";
  setText("maturityUpdatedAt", payload.generated_at ? `최근 계산 ${formatDateTimeShort(payload.generated_at)}${cacheNote}` : "조회 대기");
  const positioning = payload.positioning && typeof payload.positioning === "object" ? payload.positioning : {};
  const axes = Array.isArray(payload.evaluation_axes) ? payload.evaluation_axes : [];
  const feedbackProgress = payload.feedback_progress && typeof payload.feedback_progress === "object" ? payload.feedback_progress : {};
  const officialGuard = payload.official_performance_claim_guard && typeof payload.official_performance_claim_guard === "object" ? payload.official_performance_claim_guard : {};
  const validityGate = payload.research_validity_gate && typeof payload.research_validity_gate === "object" ? payload.research_validity_gate : {};
  const validationGate = payload.validation_matrix_gate && typeof payload.validation_matrix_gate === "object" ? payload.validation_matrix_gate : {};
  const independenceAudit = payload.ai_staff_independence_audit && typeof payload.ai_staff_independence_audit === "object" ? payload.ai_staff_independence_audit : {};
  const forwardEvidence = payload.forward_operating_evidence && typeof payload.forward_operating_evidence === "object" ? payload.forward_operating_evidence : {};
  const postMarketAudit = payload.post_market_review_audit && typeof payload.post_market_review_audit === "object" ? payload.post_market_review_audit : {};
  const strategyVersion = payload.strategy_version_registry && typeof payload.strategy_version_registry === "object" ? payload.strategy_version_registry : {};
  const architectureStage = axes.find((item) => item.id === "architecture")?.stage || {};
  const performanceStage = axes.find((item) => item.id === "performance_evidence")?.stage || {};
  setText("maturityOverall", `구현건강 ${architectureScore.toFixed(1)} / 운영성숙 ${operationalMaturityScore.toFixed(1)} / 성과증거 ${performanceEvidenceScore.toFixed(1)}`);
  setText("maturityGrade", `${Number(architectureStage.level || 0)} / ${Number(performanceStage.level || 0)}`);
  setText("maturityVerdict", `${positioning.current_label || "퀀트 기반 AI 투자 연구·검증·운영 플랫폼"} · ${payload.verdict || "증거 계산 중"}`);
  setText("maturityDelta", `피드백 보완 ${feedbackProgress.label || "0/15"} · 공식 성과 ${officialGuard.allowed ? "검증 통과" : "표시 차단"}`);
  setText("maturityUpdatedAt", payload.generated_at ? `최근 계산 ${formatDateTimeShort(payload.generated_at)} · 구현·운영·성과를 분리 평가` : "조회 대기");
  const areas = Array.isArray(payload.areas) ? payload.areas : [];
  const evidenceRows = [
    {
      id: "research_validity",
      label: "연구 유효성 게이트",
      score: Number(validityGate.score || 0),
      status: validityGate.ready ? "통과" : "성과 주장 차단",
      detail: `${Array.isArray(validityGate.blockers) ? validityGate.blockers.length : 0}개 미충족 · 미래참조·생존편향·비용·유동성 검사`,
      baseline: 100,
    },
    {
      id: "validation_matrix",
      label: "OOS·워크포워드·시장국면",
      score: Number(validationGate.score || 0),
      status: validationGate.ready ? "통과" : "검증 진행 중",
      detail: `${Array.isArray(validationGate.blockers) ? validationGate.blockers.length : 0}개 미충족 · 검증 결과를 한 표로 대사`,
      baseline: 100,
    },
    {
      id: "ai_independence",
      label: "AI 직원 독립성·근거 품질",
      score: Number(independenceAudit.score || 0),
      status: independenceAudit.independence_verified ? "독립성 검증" : "모델 출처 미검증",
      detail: `발언자 ${Number(independenceAudit.speaker_count || 0)}명 · 근거율 ${Number(independenceAudit.evidence_coverage_pct || 0).toFixed(1)}% · 모델출처 ${Number(independenceAudit.model_provenance_count || 0)}개`,
      baseline: 100,
    },
    {
      id: "forward_evidence",
      label: "장기 Paper·실전 대사 증거",
      score: Number(forwardEvidence.score || 0),
      status: forwardEvidence.ready ? "장기 증거 충족" : "증거 축적 중",
      detail: `과거장 ${Number(forwardEvidence.paper_replay_count || 0)}건 · 순방향 ${Number(forwardEvidence.forward_days || 0)}일 · 운영이력 ${Number(forwardEvidence.monitoring_days || 0)}일`,
      baseline: 100,
    },
    {
      id: "post_market_review",
      label: "장마감 10회 복기·학습 대사",
      score: Number(postMarketAudit.score || 0),
      status: postMarketAudit.ready ? "복기와 학습 연결 통과" : "연결 보완 필요",
      detail: `${Number(postMarketAudit.completed_repeats || 0)}회 완료 · 차단 ${Array.isArray(postMarketAudit.blockers) ? postMarketAudit.blockers.length : 0}개`,
      baseline: 100,
    },
    {
      id: "strategy_version",
      label: "전략 버전·승격·롤백 원장",
      score: strategyVersion.version_id ? 100 : 0,
      status: strategyVersion.state || "전략 버전 대기",
      detail: `${strategyVersion.version_id || "버전 없음"} · 롤백 ${strategyVersion.rollback_possible ? "가능" : "대상 없음"} · 실전 승격 차단`,
      baseline: 100,
    },
  ];
  const rows = [
    ...axes.map((axis) => ({ ...axis, baseline: Number(axis.score || 0), is_axis: true })),
    ...evidenceRows,
    ...areas,
  ];
  const rowNode = el("#maturityScoreRows");
  if (rowNode) {
    rowNode.innerHTML = rows.length ? rows.map((area) => {
      const score = Number(area.score || 0);
      const baseline = Number(area.baseline || 0);
      const diff = score - baseline;
      return `
        <article class="${maturityScoreClass(score)}">
          <div class="maturity-row-top">
            <strong>${escapeHtml(area.label || "-")}</strong>
            <b>${score.toFixed(1)}</b>
          </div>
          <div class="maturity-bar"><i style="width:${Math.max(0, Math.min(score, 100)).toFixed(1)}%"></i></div>
          <span>${escapeHtml(area.status || "-")} · 기준 대비 ${diff >= 0 ? "+" : ""}${diff.toFixed(1)}점</span>
          <small>${escapeHtml(area.detail || "")}</small>
        </article>
      `;
    }).join("") : `<article class="weak"><strong>점수 대기</strong><small>완성도 점수를 불러오면 분야별 진행도가 표시됩니다.</small></article>`;
  }
  const nextNode = el("#maturityNextRows");
  const next = Array.isArray(payload.next_focus) ? payload.next_focus : [];
  if (nextNode) {
    nextNode.innerHTML = next.length ? next.map((item, index) => `
      <article>
        <b>${index + 1}</b>
        <span>${escapeHtml(item)}</span>
      </article>
    `).join("") : `<article><b>-</b><span>다음 보완 과제 계산 대기</span></article>`;
  }
}

async function loadCodexstockMaturity(silent = true) {
  try {
    const query = silent ? "record=0&cache=1" : "record=1&refresh=1";
    const response = await fetch(`/api/codexstock/maturity?${query}`);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.error || result.message || "완성도 점수 조회 실패");
    renderCodexstockMaturity(result);
    if (!silent) addLog(`코덱스스톡 완성도 재계산: ${Number(result.overall_score || 0).toFixed(1)}점 · ${result.verdict || "-"}`);
    return result;
  } catch (error) {
    setText("maturityOverall", "조회 실패");
    setText("maturityVerdict", error.message);
    if (!silent) addLog(`완성도 점수 조회 실패: ${error.message}`);
    return null;
  }
}

function relaxConditionScreener() {
  const preset = el("#conditionPreset");
  if (preset) preset.value = "custom";
  setConditionInputValue("#conditionMinAmount", Math.max(0, readConditionNumber("#conditionMinAmount", 3) - 2));
  setConditionInputValue("#conditionMinChange", readConditionNumber("#conditionMinChange", -3) - 1);
  setConditionInputValue("#conditionMaxChange", readConditionNumber("#conditionMaxChange", 30) + 2);
  setConditionInputValue("#conditionMinPower", Math.max(0, readConditionNumber("#conditionMinPower", 110) - 10));
  setConditionInputValue("#conditionMinBuyRate", Math.max(0, readConditionNumber("#conditionMinBuyRate", 50) - 5));
  setConditionInputValue("#conditionMaxSellRate", Math.min(100, readConditionNumber("#conditionMaxSellRate", 85) + 5));
  setConditionInputValue("#conditionMinScore", Math.max(0, readConditionNumber("#conditionMinScore", 45) - 5));
  loadConditionScreener(false);
}

function updateConditionAutoRefresh() {
  if (state.conditionScreenerTimer) {
    window.clearInterval(state.conditionScreenerTimer);
    state.conditionScreenerTimer = null;
  }
  if (el("#conditionAutoRefresh")?.checked) {
    state.conditionScreenerTimer = window.setInterval(() => loadConditionScreener(true), 60000);
    addLog("조건검색기 자동갱신 ON: 60초마다 조건에 맞는 종목을 다시 찾습니다.");
  }
}

function syncPriceChartWindowOnDataChange(symbol = state.active) {
  const prices = state.history.get(symbol) || [];
  const total = prices.length;
  if (!total) return;
  const view = state.priceChart;
  const previousTotal = Number(view.total || 0);
  const wasPinnedToLatest = previousTotal > 0 && (view.end ?? -1) >= previousTotal - 1;
  const shouldResetToLatest = (
    view.symbol !== symbol ||
    view.end === null ||
    view.end >= total ||
    view.start >= total ||
    previousTotal === 0 ||
    (previousTotal !== total && wasPinnedToLatest)
  );
  if (shouldResetToLatest) {
    const windowSize = Math.min(total, 160);
    view.symbol = symbol;
    view.start = Math.max(0, total - windowSize);
    view.end = total - 1;
    view.hoverX = null;
  }
  view.total = total;
}

function setPriceChartWindow(size) {
  const prices = state.history.get(state.active) || [];
  const total = prices.length;
  if (!total) return;
  const view = state.priceChart;
  view.symbol = state.active;
  view.total = total;
  const windowSize = size === "all" ? total : Math.min(total, Math.max(10, Number(size || 160)));
  view.start = Math.max(0, total - windowSize);
  view.end = total - 1;
  view.hoverX = null;
  drawChart();
}

function priceChartWindowSize() {
  const view = state.priceChart;
  return Math.max(10, (view.end ?? 0) - view.start + 1);
}

function zoomPriceChart(direction) {
  const prices = state.history.get(state.active) || [];
  const total = prices.length;
  if (!total) return;
  syncPriceChartWindowOnDataChange(state.active);
  const view = state.priceChart;
  const current = priceChartWindowSize();
  const next = Math.max(20, Math.min(total, Math.round(current * (direction < 0 ? 0.72 : 1.38))));
  const anchor = Math.min(total - 1, Math.max(0, view.end ?? total - 1));
  view.end = anchor;
  view.start = Math.max(0, anchor - next + 1);
  if (view.end - view.start + 1 < next) view.end = Math.min(total - 1, view.start + next - 1);
  drawChart();
}

function panPriceChart(delta) {
  const prices = state.history.get(state.active) || [];
  const total = prices.length;
  if (!total) return;
  syncPriceChartWindowOnDataChange(state.active);
  const view = state.priceChart;
  const size = priceChartWindowSize();
  const nextStart = Math.max(0, Math.min(total - size, view.start + delta));
  view.start = nextStart;
  view.end = nextStart + size - 1;
  drawChart();
}

function updatePriceChartViewportLabel(dates, prices, source) {
  const view = state.priceChart;
  const total = prices.length;
  if (!total) return setText("priceChartViewport", "차트 데이터 대기");
  const startDate = dates[view.start] || "-";
  const endDate = dates[view.end ?? total - 1] || "-";
  const close = prices[view.end ?? total - 1] || 0;
  setText("priceChartViewport", `${startDate} ~ ${endDate} · ${priceChartWindowSize()}개 봉 · 종가 ${money(close)} · ${source || "데이터"}`);
}

function updateChartMoneyStrip(visiblePrices, dates, start, end) {
  if (!visiblePrices.length) return;
  const first = Number(visiblePrices[0] || 0);
  const last = Number(visiblePrices[visiblePrices.length - 1] || 0);
  const high = Math.max(...visiblePrices);
  const low = Math.min(...visiblePrices);
  const change = last - first;
  const changePct = first ? ((last / first) - 1) * 100 : 0;
  setText("chartMoneyLast", money(last));
  setText("chartMoneyHigh", `${money(high)} · ${shortDateLabel(dates[start + visiblePrices.indexOf(high)])}`);
  setText("chartMoneyLow", `${money(low)} · ${shortDateLabel(dates[start + visiblePrices.indexOf(low)])}`);
  setText("chartMoneyChange", `${signedMoney(change)} (${pct(changePct)})`);
  const changeNode = el("#chartMoneyChange");
  if (changeNode) changeNode.className = quoteClass(changePct);
}

function drawMainChartLine(ctx, values, indexes, box, color, lineWidth = 2) {
  const { left, top, chartWidth, chartHeight, min, range } = box;
  ctx.beginPath();
  let hasPoint = false;
  indexes.forEach((sourceIndex, visibleIndex) => {
    const value = values[sourceIndex];
    if (value === null || value === undefined || Number.isNaN(Number(value))) return;
    const x = left + (visibleIndex / Math.max(1, indexes.length - 1)) * chartWidth;
    const y = top + chartHeight - ((Number(value) - min) / range) * chartHeight;
    if (!hasPoint) {
      ctx.moveTo(x, y);
      hasPoint = true;
    } else {
      ctx.lineTo(x, y);
    }
  });
  if (!hasPoint) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}

function drawChart() {
  const canvas = el("#priceChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const prices = (state.history.get(state.active) || []).map(Number).filter((value) => Number.isFinite(value) && value > 0);
  if (!prices.length) {
    ctx.clearRect(0, 0, width, height);
    setText("priceChartViewport", "차트 데이터 대기");
    return;
  }
  syncPriceChartWindowOnDataChange(state.active);
  const dates = state.historyDates.get(state.active) || makeFallbackDates(prices.length);
  const source = state.historySource.get(state.active) || "";
  const view = state.priceChart;
  const start = Math.max(0, Math.min(prices.length - 1, view.start));
  const end = Math.max(start, Math.min(prices.length - 1, view.end ?? prices.length - 1));
  view.start = start;
  view.end = end;
  const indexes = Array.from({ length: end - start + 1 }, (_, offset) => start + offset);
  const visiblePrices = indexes.map((index) => prices[index]);
  const ma12 = movingAverage(prices, 12);
  const ma32 = movingAverage(prices, 32);
  const visibleMa = indexes.flatMap((index) => [ma12[index], ma32[index]]).filter((value) => value !== null && value !== undefined);
  const min = Math.min(...visiblePrices, ...visibleMa) * 0.998;
  const max = Math.max(...visiblePrices, ...visibleMa) * 1.002;
  const range = max - min || 1;
  const left = 92;
  const right = 96;
  const top = 34;
  const bottom = 58;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const box = { left, top, chartWidth, chartHeight, min, range };

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#060a0f";
  ctx.fillRect(0, 0, width, height);
  updateChartMoneyStrip(visiblePrices, dates, start, end);
  ctx.strokeStyle = "rgba(84, 215, 255, .14)";
  ctx.lineWidth = 1;

  for (let i = 0; i <= 5; i += 1) {
    const y = top + (chartHeight / 5) * i;
    const value = max - (range / 5) * i;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(left + chartWidth, y);
    ctx.stroke();
    ctx.fillStyle = "rgba(176, 197, 212, .78)";
    ctx.font = "12px Consolas";
    ctx.textAlign = "right";
    ctx.fillText(money(value), left - 8, y + 4);
    ctx.textAlign = "left";
    ctx.fillText(money(value), left + chartWidth + 8, y + 4);
  }

  const tickCount = Math.min(8, Math.max(4, Math.floor(chartWidth / 130)));
  for (let i = 0; i < tickCount; i += 1) {
    const ratio = tickCount === 1 ? 0 : i / (tickCount - 1);
    const visibleIndex = Math.round(ratio * (indexes.length - 1));
    const sourceIndex = indexes[visibleIndex];
    const x = left + ratio * chartWidth;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, top + chartHeight);
    ctx.stroke();
    ctx.fillStyle = "rgba(176, 197, 212, .82)";
    ctx.font = "12px Consolas";
    ctx.textAlign = "center";
    ctx.fillText(shortDateLabel(dates[sourceIndex]), x, height - 22);
  }

  drawMainChartLine(ctx, prices, indexes, box, "#54d7ff", 3);
  drawMainChartLine(ctx, ma12, indexes, box, "#ffb547", 2);
  drawMainChartLine(ctx, ma32, indexes, box, "#77e1b8", 2);

  const lastPrice = prices[end];
  const lastY = top + chartHeight - ((lastPrice - min) / range) * chartHeight;
  ctx.strokeStyle = "rgba(255,255,255,.24)";
  ctx.setLineDash([5, 5]);
  ctx.beginPath();
  ctx.moveTo(left, lastY);
  ctx.lineTo(left + chartWidth, lastY);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#eaf6ff";
  ctx.font = "bold 13px Consolas";
  const lastLabel = money(lastPrice);
  const lastLabelWidth = ctx.measureText(lastLabel).width + 18;
  ctx.fillStyle = "rgba(84, 215, 255, .20)";
  ctx.strokeStyle = "rgba(84, 215, 255, .42)";
  ctx.fillRect(left + chartWidth + 6, lastY - 13, lastLabelWidth, 24);
  ctx.strokeRect(left + chartWidth + 6, lastY - 13, lastLabelWidth, 24);
  ctx.fillStyle = "#eaf6ff";
  ctx.textAlign = "left";
  ctx.fillText(lastLabel, left + chartWidth + 15, lastY + 4);

  const high = Math.max(...visiblePrices);
  const low = Math.min(...visiblePrices);
  const highVisibleIndex = visiblePrices.indexOf(high);
  const lowVisibleIndex = visiblePrices.indexOf(low);
  [
    { label: `고 ${money(high)}`, index: highVisibleIndex, value: high, color: "#ffb547" },
    { label: `저 ${money(low)}`, index: lowVisibleIndex, value: low, color: "#77e1b8" },
  ].forEach((mark) => {
    const x = left + (mark.index / Math.max(1, indexes.length - 1)) * chartWidth;
    const y = top + chartHeight - ((mark.value - min) / range) * chartHeight;
    ctx.fillStyle = mark.color;
    ctx.beginPath();
    ctx.arc(x, y, 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.font = "bold 12px Consolas";
    ctx.textAlign = x > left + chartWidth - 120 ? "right" : "left";
    ctx.fillText(mark.label, x + (ctx.textAlign === "right" ? -8 : 8), y - 8);
  });

  if (view.hoverX !== null) {
    const x = Math.max(left, Math.min(left + chartWidth, view.hoverX));
    const ratio = (x - left) / Math.max(1, chartWidth);
    const visibleIndex = Math.round(ratio * (indexes.length - 1));
    const sourceIndex = indexes[visibleIndex];
    const price = prices[sourceIndex];
    const date = dates[sourceIndex] || "-";
    const y = top + chartHeight - ((price - min) / range) * chartHeight;
    ctx.strokeStyle = "rgba(234,246,255,.55)";
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, top + chartHeight);
    ctx.stroke();
    ctx.fillStyle = "#eaf6ff";
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
    const ma12Value = ma12[sourceIndex];
    const ma32Value = ma32[sourceIndex];
    const prev = sourceIndex > 0 ? prices[sourceIndex - 1] : price;
    const dayChange = price - prev;
    const dayChangePct = prev ? ((price / prev) - 1) * 100 : 0;
    const lines = [
      `${date}`,
      `가격 ${money(price)}`,
      `전일대비 ${signedMoney(dayChange)} (${pct(dayChangePct)})`,
      `MA12 ${ma12Value ? money(ma12Value) : "-"} · MA32 ${ma32Value ? money(ma32Value) : "-"}`,
    ];
    const boxWidth = Math.max(...lines.map((line) => ctx.measureText(line).width)) + 22;
    const boxHeight = 78;
    const tx = x > left + chartWidth - boxWidth - 12 ? x - boxWidth - 10 : x + 10;
    ctx.fillStyle = "rgba(6,10,15,.92)";
    ctx.strokeStyle = "rgba(84,215,255,.35)";
    ctx.fillRect(tx, top + 8, boxWidth, boxHeight);
    ctx.strokeRect(tx, top + 8, boxWidth, boxHeight);
    ctx.fillStyle = "#eaf6ff";
    ctx.textAlign = "left";
    ctx.font = "12px Consolas";
    lines.forEach((line, index) => {
      ctx.fillStyle = index === 2 ? (dayChange >= 0 ? "#ff6b6b" : "#54d7ff") : "#eaf6ff";
      ctx.fillText(line, tx + 11, top + 27 + index * 16);
    });
  }

  updatePriceChartViewportLabel(dates, prices, source);
}

function bindMainPriceChartControls() {
  const canvas = el("#priceChart");
  if (!canvas) return;
  document.querySelectorAll("[data-main-chart-window]").forEach((button) => {
    button.addEventListener("click", () => setPriceChartWindow(button.dataset.mainChartWindow));
  });
  el("#priceChartZoomIn")?.addEventListener("click", () => zoomPriceChart(-1));
  el("#priceChartZoomOut")?.addEventListener("click", () => zoomPriceChart(1));
  el("#priceChartPanLeft")?.addEventListener("click", () => panPriceChart(-Math.max(8, Math.round(priceChartWindowSize() * 0.35))));
  el("#priceChartPanRight")?.addEventListener("click", () => panPriceChart(Math.max(8, Math.round(priceChartWindowSize() * 0.35))));

  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    zoomPriceChart(event.deltaY < 0 ? -1 : 1);
  }, { passive: false });

  canvas.addEventListener("pointerdown", (event) => {
    const view = state.priceChart;
    view.dragging = true;
    view.dragStartX = event.clientX;
    view.dragStartStart = view.start;
    view.dragStartEnd = view.end ?? (state.history.get(state.active) || []).length - 1;
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener("pointermove", (event) => {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / Math.max(1, rect.width);
    const view = state.priceChart;
    view.hoverX = (event.clientX - rect.left) * scaleX;
    if (view.dragging) {
      const prices = state.history.get(state.active) || [];
      const total = prices.length;
      const size = Math.max(1, view.dragStartEnd - view.dragStartStart + 1);
      const deltaPx = event.clientX - view.dragStartX;
      const deltaPoints = Math.round((-deltaPx / Math.max(1, rect.width)) * size);
      const nextStart = Math.max(0, Math.min(total - size, view.dragStartStart + deltaPoints));
      view.start = nextStart;
      view.end = nextStart + size - 1;
    }
    drawChart();
  });

  canvas.addEventListener("pointerup", (event) => {
    state.priceChart.dragging = false;
    try { canvas.releasePointerCapture(event.pointerId); } catch (_) {}
  });

  canvas.addEventListener("pointerleave", () => {
    state.priceChart.dragging = false;
    state.priceChart.hoverX = null;
    drawChart();
  });
}

function movingAverage(values, window) {
  return values.map((_, index) => {
    if (index + 1 < window) return null;
    const chunk = values.slice(index + 1 - window, index + 1);
    return chunk.reduce((sum, item) => sum + item, 0) / window;
  });
}

function normalizeToPrice(values, priceValues) {
  const minPrice = Math.min(...priceValues);
  const maxPrice = Math.max(...priceValues);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  return values.map((value) => minPrice + ((value - minValue) / ((maxValue - minValue) || 1)) * (maxPrice - minPrice));
}

function getChoseong(text) {
  const initials = ["\u3131", "\u3132", "\u3134", "\u3137", "\u3138", "\u3139", "\u3141", "\u3142", "\u3143", "\u3145", "\u3146", "\u3147", "\u3148", "\u3149", "\u314a", "\u314b", "\u314c", "\u314d", "\u314e"];
  return [...String(text)].map((char) => {
    const code = char.charCodeAt(0) - 44032;
    if (code < 0 || code > 11171) return char.toUpperCase();
    return initials[Math.floor(code / 588)];
  }).join("");
}

function symbolMatchesQuery(item, query) {
  const q = compactSearchText(query);
  if (!q) return true;
  const name = compactSearchText(item.name);
  const symbol = compactSearchText(item.symbol);
  const cho = compactSearchText(`${item.choseong || ""} ${getChoseong(item.name || "")}`);
  return name.includes(q) || symbol.includes(q) || cho.includes(q);
}

function symbolSearchScore(item, query) {
  const q = compactSearchText(query);
  const name = compactSearchText(item.name);
  const symbol = compactSearchText(item.symbol);
  const cho = compactSearchText(`${item.choseong || ""} ${getChoseong(item.name || "")}`);
  if (!q) return 20;
  if (name === q) return 0;
  if (symbol === q) return 1;
  if (cho === q) return 2;
  if (name.startsWith(q)) return 3;
  if (cho.startsWith(q)) return 4;
  if (symbol.startsWith(q)) return 5;
  return 20;
}

function searchSymbols(query) {
  const q = compactSearchText(query);
  const universe = searchableUniverse();
  const rows = q ? universe.filter((item) => symbolMatchesQuery(item, q)) : universe;
  return rows
    .map((item) => ({ item, score: symbolSearchScore(item, q) }))
    .sort((a, b) => a.score - b.score || String(a.item.market || "").localeCompare(String(b.item.market || "")) || String(a.item.name || "").localeCompare(String(b.item.name || "")))
    .map((row) => row.item)
    .slice(0, q ? 80 : 50);
}

function countSymbolMatches(query) {
  const q = compactSearchText(query);
  const universe = searchableUniverse();
  if (!q) return universe.length;
  return universe.filter((item) => symbolMatchesQuery(item, q)).length;
}

function resolveSymbolInput(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const bracketSymbol = raw.match(/\(([A-Z0-9.]{1,16})\)$/i);
  if (bracketSymbol) return normalizeSymbol(bracketSymbol[1]);
  const normalized = normalizeSymbol(raw);
  const q = compactSearchText(raw);
  const universe = searchableUniverse();
  const exact = universe.find((item) => normalizeSymbol(item.symbol) === normalized)
    || universe.find((item) => compactSearchText(item.name) === q)
    || universe.find((item) => compactSearchText(item.choseong || "") === q);
  if (exact) return normalizeSymbol(exact.symbol);
  return normalizeSymbol(searchSymbols(raw)[0]?.symbol || raw);
}

async function loadUniverse() {
  try {
    const response = await fetch("/api/universe");
    const result = await response.json();
    if (!response.ok || !Array.isArray(result.rows)) return;
    const existing = new Set(researchUniverse.map((item) => item.symbol));
    result.rows.forEach((item) => {
      const symbol = String(item.symbol || "").toUpperCase();
      if (!symbol || existing.has(symbol)) return;
      existing.add(symbol);
      researchUniverse.push({
        symbol,
        name: item.name || symbol,
        market: item.market || "",
        choseong: item.choseong || symbol,
      });
    });
    state.universeStats = { count: result.count || researchUniverse.length, source: result.source || "내장" };
    addLog(`종목 마스터 갱신: ${result.count || researchUniverse.length}개 (${result.source || "내장"})`);
    buildWatchRows("#watchRows");
    buildWatchRows("#watchRowsTrading");
    buildTicker();
    renderSelectedSymbols();
    renderReplaySelectedSymbols();
    renderMarket();
  } catch (error) {
    addLog("종목 마스터는 내장 목록으로 실행 중입니다.");
  }
}

async function loadWatchlist(syncKis = false) {
  try {
    const response = await fetch(syncKis ? "/api/watchlist?sync=kis" : "/api/watchlist");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "관심종목 조회 실패");
    const nextSymbols = (result.symbols || []).map((item) => normalizeSymbol(item));
    state.watchlist = result.rows || [];
    syncSymbols(nextSymbols);
    const sync = result.kis_sync || {};
    const syncText = sync.synced_at
      ? ` · 한투 ${sync.ok ? "동기화" : "확인필요"} ${sync.synced_at}`
      : "";
    setText("watchlistMeta", `${result.count || nextSymbols.length}개 관심종목 · 로컬+한투 저장${syncText}`);
  } catch (error) {
    setText("watchlistMeta", `관심종목 기본값 사용 · ${error.message}`);
  }
}

async function syncKisWatchlist(silent = false) {
  try {
    if (!silent) setText("watchlistMeta", "한투 MTS/HTS 관심종목을 동기화하는 중입니다.");
    const response = await fetch("/api/watchlist/kis-sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "web" }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "한투 관심종목 동기화 실패");
    const nextSymbols = (result.symbols || []).map((item) => normalizeSymbol(item));
    state.watchlist = result.rows || [];
    syncSymbols(nextSymbols);
    buildWatchRows("#watchRows");
    buildWatchRows("#watchRowsTrading");
    const sync = result.kis_sync || {};
    setText("watchlistMeta", `${result.count || nextSymbols.length}개 관심종목 · ${sync.message || "한투 동기화 완료"}`);
    if (!silent) addLog(sync.message || "한투 MTS/HTS 관심종목 동기화 완료");
    return result;
  } catch (error) {
    if (!silent) addLog(`한투 관심종목 동기화 실패: ${error.message}`);
    setText("watchlistMeta", `한투 동기화 확인 필요 · ${error.message}`);
    return null;
  }
}

async function saveWatchlistSymbol(action, symbol) {
  const normalized = action === "add" ? resolveSymbolInput(symbol) : normalizeSymbol(symbol);
  if (!normalized) return addLog("추가/삭제할 종목을 입력해주세요.");
  try {
    const response = await fetch("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, symbol: normalized }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "관심종목 저장 실패");
    const nextSymbols = (result.symbols || []).map((item) => normalizeSymbol(item));
    state.watchlist = result.rows || [];
    syncSymbols(nextSymbols);
    if (!symbols.includes(state.active)) state.active = symbols[0] || "083450";
    await tickMarket();
    const meta = symbolMeta(normalized);
    addLog(`관심종목 ${action === "add" ? "추가" : "삭제"}: ${meta.name}`);
  } catch (error) {
    addLog(`관심종목 저장 실패: ${error.message}`);
  }
}

function renderRecommendations(rows = []) {
  const node = el("#recommendRows");
  if (!node) return;
  state.recommendations = rows;
  node.innerHTML = rows.length
    ? rows.slice(0, 6).map((row) => {
      const meta = symbolMeta(row.symbol, row);
      return `
      <div class="recommend-card">
        <strong>${escapeHtml(meta.name)}</strong>
        <small>${escapeHtml(symbolSubLabel(meta))} · 점수 ${Number(row.score || 0).toFixed(1)} · ${escapeHtml(row.action || "-")} · 게이트 ${escapeHtml(row.risk_gate_status || "-")}</small>
        <small>${(row.reasons || []).slice(0, 2).join(" · ") || "AI 후보 발굴 결과"}</small>
        <button class="recommend-add" data-watch-add="${escapeHtml(meta.symbol)}">관심종목 추가</button>
      </div>
    `;
    }).join("")
    : `<div class="recommend-card"><strong>추천 대기</strong><small>추천 갱신을 누르면 AI 후보 상위 종목이 표시됩니다.</small></div>`;
}

async function loadRecommendations(force = false) {
  try {
    const response = await fetch(force ? "/api/agent/screener?force=1" : "/api/agent/screener");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "추천종목 조회 실패");
    renderRecommendations(result.candidates || []);
    if (force) addLog(`AI 추천종목 갱신: ${result.top?.symbol ? symbolDisplayName(result.top.symbol, result.top) : "-"}`);
  } catch (error) {
    renderRecommendations([]);
    addLog(`AI 추천종목 조회 실패: ${error.message}`);
  }
}

function renderSelectedSymbols() {
  const box = el("#selectedSymbols");
  if (!box) return;
  box.innerHTML = state.selectedResearchSymbols.map((symbol) => {
    const item = symbolMeta(symbol);
    const activeClass = symbol === (el("#symbol")?.value || state.selectedResearchSymbols[0] || "").toUpperCase() ? " active" : "";
    return `<button class="symbol-chip${activeClass}" data-primary-symbol="${symbol}" title="${escapeHtml(item.name)} 선택">
      <strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(symbolSubLabel(item))}</span><i data-remove-symbol="${symbol}" title="비교 목록에서 제거">×</i>
    </button>`;
  }).join("");
  syncPrimaryResearchSymbol(state.selectedResearchSymbols[0] || "AAPL", false);
}

function syncPrimaryResearchSymbol(symbol, rerun = true) {
  const normalized = String(symbol || "AAPL").toUpperCase();
  state.active = normalized;
  if (el("#symbol")) el("#symbol").value = normalized;
  document.querySelectorAll(".symbol-chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.primarySymbol === normalized);
  });
  const item = researchUniverse.find((entry) => entry.symbol === normalized);
  if (item) setText("strategyChartNote", `${item.name} 선택됨 · 백테스트를 준비합니다.`);
  loadLivePilotPlan(true);
  if (rerun) {
    runBacktest();
    runMultiBacktest();
    runRobustness();
    runProtections();
  }
}

function selectedPreset() {
  const id = el("#strategyPreset")?.value || strategyPresets[0].id;
  return strategyPresets.find((preset) => preset.id === id) || strategyPresets[0];
}

function renderStrategyPresets() {
  const select = el("#strategyPreset");
  if (!select) return;
  select.innerHTML = strategyPresets.map((preset) => `
    <option value="${preset.id}">${preset.name} · ${preset.owner}</option>
  `).join("");
  select.value = strategyPresets[0].id;
  applyStrategyPreset(false);
}

function applyStrategyPreset(announce = true) {
  const preset = selectedPreset();
  if (!preset) return;
  el("#fast").value = preset.fast;
  el("#slow").value = preset.slow;
  setText("strategyChartNote", `${preset.name} · ${preset.owner} · MA ${preset.fast}/${preset.slow} · ${preset.memo}`);
  if (announce) addLog(`전략 선택: ${preset.name} (${preset.owner})`);
}

function renderSymbolDropdown(query) {
  const dropdown = el("#symbolDropdown");
  if (!dropdown) return;
  const matches = searchSymbols(query);
  const matchCount = countSymbolMatches(query);
  dropdown.innerHTML = `
    <div class="symbol-dropdown-meta">
      전체 ${Number(state.universeStats.count || researchUniverse.length).toLocaleString()}개 · 검색결과 ${matchCount.toLocaleString()}개 · 상위 ${matches.length}개 표시
      <small>${state.universeStats.source || "내장"}</small>
    </div>
  ` + matches.map((item) => `
    <button class="symbol-option" data-add-symbol="${item.symbol}">
      <strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.market || "시장 확인")}</span><small>초성 ${escapeHtml(item.choseong || "-")}</small>
    </button>
  `).join("");
  dropdown.classList.toggle("open", matches.length > 0 && document.activeElement === el("#symbolSearch"));
}

function syncReplaySymbolsInput() {
  const input = el("#replaySymbols");
  if (input) input.value = state.replaySelectedSymbols.join(",");
}

function renderReplaySelectedSymbols() {
  const box = el("#replaySelectedSymbols");
  if (!box) return;
  syncReplaySymbolsInput();
  box.innerHTML = state.replaySelectedSymbols.map((symbol) => {
    const item = symbolMeta(symbol);
    return `<button class="symbol-chip replay-chip" data-replay-primary="${escapeHtml(symbol)}" title="${escapeHtml(item.name)} 훈련 종목">
      <strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(symbolSubLabel(item))}</span><i data-replay-symbol-remove="${escapeHtml(symbol)}" title="훈련 목록에서 제거">×</i>
    </button>`;
  }).join("");
}

function renderReplaySymbolDropdown(query) {
  const dropdown = el("#replaySymbolDropdown");
  const input = el("#replaySymbolSearch");
  if (!dropdown || !input) return;
  const matches = searchSymbols(query);
  const matchCount = countSymbolMatches(query);
  dropdown.innerHTML = `
    <div class="symbol-dropdown-meta">
      훈련 종목 검색 · 전체 ${Number(state.universeStats.count || researchUniverse.length).toLocaleString()}개 · 검색결과 ${matchCount.toLocaleString()}개
      <small>이름, 초성, 영문명으로 검색 가능 · ${state.universeStats.source || "내장"}</small>
    </div>
  ` + matches.map((item) => `
    <button class="symbol-option" data-replay-symbol-pick="${escapeHtml(item.symbol)}">
      <strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.market || "시장 확인")}</span><small>초성 ${escapeHtml(item.choseong || "-")}</small>
    </button>
  `).join("");
  dropdown.classList.toggle("open", matches.length > 0 && document.activeElement === input);
}

function addReplaySymbol(symbol) {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) return;
  state.replaySelectedSymbols = [normalized, ...state.replaySelectedSymbols.filter((item) => item !== normalized)].slice(0, 10);
  renderReplaySelectedSymbols();
  const input = el("#replaySymbolSearch");
  if (input) input.value = "";
  renderReplaySymbolDropdown("");
  el("#replaySymbolDropdown")?.classList.remove("open");
}

function removeReplaySymbol(symbol) {
  const normalized = normalizeSymbol(symbol);
  state.replaySelectedSymbols = state.replaySelectedSymbols.filter((item) => item !== normalized);
  if (!state.replaySelectedSymbols.length) state.replaySelectedSymbols = [...state.selectedResearchSymbols.slice(0, 3)];
  renderReplaySelectedSymbols();
}

function applyReplayStrategyDefaults() {
  const strategy = el("#replayStrategy")?.value || "ma_cross";
  const defaults = {
    ma_cross: { fast: 12, slow: 32, stop: 8, take: 0, hold: 0 },
    protected_ma: { fast: 12, slow: 32, stop: 6, take: 18, hold: 0 },
    short_swing: { fast: 5, slow: 20, stop: 5, take: 10, hold: 20 },
    breakout: { fast: 10, slow: 50, stop: 7, take: 22, hold: 45 },
    intraday_theme_leader: { fast: 3, slow: 8, stop: 1.8, take: 2.2, hold: 3, cycles: 240 },
  };
  const preset = defaults[strategy] || defaults.ma_cross;
  if (el("#fast")) el("#fast").value = preset.fast;
  if (el("#slow")) el("#slow").value = preset.slow;
  if (el("#replayStopLoss")) el("#replayStopLoss").value = preset.stop;
  if (el("#replayTakeProfit")) el("#replayTakeProfit").value = preset.take;
  if (el("#replayHoldingLimit")) el("#replayHoldingLimit").value = preset.hold;
  if (el("#replayCyclesPerDay") && preset.cycles) el("#replayCyclesPerDay").value = preset.cycles;
  addLog(`과거장 훈련 전략 선택: ${el("#replayStrategy")?.selectedOptions?.[0]?.textContent || strategy}`);
}

function closeWatchlistDropdown() {
  const dropdown = el("#watchlistDropdown");
  if (dropdown) dropdown.classList.remove("open");
  state.watchlistSearchIndex = -1;
}

function updateWatchlistSearchFocus() {
  const options = Array.from(document.querySelectorAll("#watchlistDropdown [data-watch-select]"));
  options.forEach((button, index) => button.classList.toggle("active", index === state.watchlistSearchIndex));
  const active = options[state.watchlistSearchIndex];
  if (active) active.scrollIntoView({ block: "nearest" });
}

function renderWatchlistDropdown(query) {
  const dropdown = el("#watchlistDropdown");
  const input = el("#watchlistInput");
  if (!dropdown || !input) return;
  const matches = searchSymbols(query);
  const matchCount = countSymbolMatches(query);
  state.watchlistSearchIndex = -1;
  dropdown.innerHTML = `
    <div class="symbol-dropdown-meta">
      관심종목 검색 · 전체 ${Number(state.universeStats.count || researchUniverse.length).toLocaleString()}개 · 검색결과 ${matchCount.toLocaleString()}개
      <small>이름, 초성, 영문명으로 검색 가능 · ${state.universeStats.source || "내장"}</small>
    </div>
  ` + matches.map((item) => `
    <button class="symbol-option" data-watch-select="${escapeHtml(item.symbol)}">
      <strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.market || "시장 확인")}</span><small>초성 ${escapeHtml(item.choseong || "-")}</small>
    </button>
  `).join("");
  dropdown.classList.toggle("open", matches.length > 0 && document.activeElement === input);
}

async function chooseWatchlistSymbol(symbol) {
  const normalized = normalizeSymbol(symbol);
  const meta = symbolMeta(normalized);
  const input = el("#watchlistInput");
  if (input) input.value = usefulSymbolName(meta.name, normalized) ? `${meta.name} (${normalized})` : normalized;
  closeWatchlistDropdown();
  await saveWatchlistSymbol("add", normalized);
}

function addWatchlistFromInput() {
  const input = el("#watchlistInput");
  const normalized = resolveSymbolInput(input?.value || "");
  closeWatchlistDropdown();
  saveWatchlistSymbol("add", normalized);
}

function handleWatchlistSearchKeydown(event) {
  const dropdown = el("#watchlistDropdown");
  const options = Array.from(document.querySelectorAll("#watchlistDropdown [data-watch-select]"));
  if (event.key === "Escape") {
    closeWatchlistDropdown();
    return;
  }
  if (event.key === "ArrowDown" && options.length) {
    event.preventDefault();
    state.watchlistSearchIndex = Math.min(options.length - 1, state.watchlistSearchIndex + 1);
    updateWatchlistSearchFocus();
    return;
  }
  if (event.key === "ArrowUp" && options.length) {
    event.preventDefault();
    state.watchlistSearchIndex = Math.max(0, state.watchlistSearchIndex - 1);
    updateWatchlistSearchFocus();
    return;
  }
  if (event.key === "Enter") {
    event.preventDefault();
    const selected = options[state.watchlistSearchIndex] || (dropdown?.classList.contains("open") ? options[0] : null);
    if (selected) chooseWatchlistSymbol(selected.dataset.watchSelect);
    else addWatchlistFromInput();
  }
}

function addResearchSymbol(symbol) {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) return;
  state.selectedResearchSymbols = [normalized, ...state.selectedResearchSymbols.filter((item) => item !== normalized)].slice(0, 8);
  renderSelectedSymbols();
  syncPrimaryResearchSymbol(normalized, true);
}

function removeResearchSymbol(symbol) {
  const normalized = normalizeSymbol(symbol);
  state.selectedResearchSymbols = state.selectedResearchSymbols.filter((item) => item !== normalized);
  if (!state.selectedResearchSymbols.length) state.selectedResearchSymbols = ["AAPL"];
  renderSelectedSymbols();
  syncPrimaryResearchSymbol(state.selectedResearchSymbols[0], true);
}

function drawCompareChart(results) {
  const canvas = el("#strategyCompareChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const legend = el("#chartLegend");
  const preset = selectedPreset();
  const left = 54;
  const right = 28;
  const top = 28;
  const bottom = 58;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#080d13";
  ctx.fillRect(0, 0, width, height);
  ctx.font = "13px Consolas, Malgun Gothic, sans-serif";
  ctx.strokeStyle = "rgba(128,151,168,.18)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 7; i += 1) {
    const x = left + (chartWidth / 6) * i;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, top + chartHeight);
    ctx.stroke();
  }
  for (let i = 0; i < 5; i += 1) {
    const y = top + (chartHeight / 4) * i;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(width - right, y);
    ctx.stroke();
  }
  const colors = ["#54d7ff", "#59d6a3", "#f0bf56", "#ff6464", "#a98cff", "#43a4ff", "#ff9f43", "#9cffac"];
  const curves = results.map((result) => ({
    symbol: result.symbol,
    name: symbolDisplayName(result.symbol, result),
    values: result.equity_curve || [],
    dates: result.dates || [],
    totalReturn: Number(result.total_return_pct || 0),
    buyHoldReturn: Number(result.buy_hold_return_pct || 0),
  })).filter((row) => row.values.length);
  const allValues = curves.flatMap((row) => row.values);
  if (!allValues.length) {
    if (legend) legend.innerHTML = `<span>표시할 백테스트 결과가 없습니다.</span>`;
    return;
  }
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;
  const primaryDates = curves.find((curve) => curve.dates.length)?.dates || [];
  curves.forEach((curve, curveIndex) => {
    ctx.beginPath();
    curve.values.forEach((value, index) => {
      const x = left + (index / Math.max(1, curve.values.length - 1)) * chartWidth;
      const y = top + chartHeight - ((value - min) / range) * chartHeight;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = colors[curveIndex % colors.length];
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.fillStyle = colors[curveIndex % colors.length];
    ctx.fillText(curve.name, left + 8 + curveIndex * 116, 20);
  });
  const tickCount = 7;
  ctx.textAlign = "center";
  ctx.fillStyle = "rgba(237,244,248,.72)";
  for (let i = 0; i < tickCount; i += 1) {
    const ratio = i / Math.max(1, tickCount - 1);
    const x = left + ratio * chartWidth;
    const dateIndex = Math.round(ratio * Math.max(0, primaryDates.length - 1));
    const raw = primaryDates[dateIndex] || "";
    const label = raw.length >= 7 ? raw.slice(0, 7) : raw;
    ctx.fillText(label, x, height - 22);
  }
  ctx.textAlign = "left";
  if (legend) {
    legend.innerHTML = curves.map((curve, index) => `
      <div class="legend-chip" style="--series-color:${colors[index % colors.length]}">
        <i></i>
        <strong>${curve.name}</strong>
        <span>${escapeHtml(symbolSubLabel(symbolMeta(curve.symbol)))}</span>
        <b>${preset.name}</b>
        <em>전략 ${pct(curve.totalReturn)} / 보유 ${pct(curve.buyHoldReturn)}</em>
      </div>
    `).join("");
  }
}

function drawCompareChart(results = null, resetView = true) {
  const canvas = el("#strategyCompareChart");
  if (!canvas) return;
  if (Array.isArray(results)) {
    state.strategyChart.results = results;
    if (resetView) {
      state.strategyChart.start = 0;
      state.strategyChart.end = null;
      state.strategyChart.hoverX = null;
    }
  }
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const legend = el("#chartLegend");
  const preset = selectedPreset();
  const left = 70;
  const right = 32;
  const top = 30;
  const bottom = 72;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const colors = ["#54d7ff", "#59d6a3", "#f0bf56", "#ff6464", "#a98cff", "#43a4ff", "#ff9f43", "#9cffac"];
  const curves = (state.strategyChart.results || []).map((result) => ({
    symbol: result.symbol,
    name: symbolDisplayName(result.symbol, result),
    values: result.equity_curve || [],
    dates: result.dates || [],
    totalReturn: Number(result.total_return_pct || 0),
    buyHoldReturn: Number(result.buy_hold_return_pct || 0),
  })).filter((row) => row.values.length);
  const totalPoints = Math.max(0, ...curves.map((curve) => curve.values.length));

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#080d13";
  ctx.fillRect(0, 0, width, height);
  ctx.font = "13px Consolas, Malgun Gothic, sans-serif";
  ctx.strokeStyle = "rgba(128,151,168,.18)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 7; i += 1) {
    const x = left + (chartWidth / 6) * i;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, top + chartHeight);
    ctx.stroke();
  }
  for (let i = 0; i < 5; i += 1) {
    const y = top + (chartHeight / 4) * i;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(width - right, y);
    ctx.stroke();
  }
  if (!totalPoints) {
    if (legend) legend.innerHTML = `<span>표시할 백테스트 결과가 없습니다.</span>`;
    updateChartViewportLabel();
    return;
  }

  normalizeStrategyChartView(totalPoints, resetView);
  const viewStart = state.strategyChart.start;
  const viewEnd = state.strategyChart.end ?? totalPoints - 1;
  const visibleCurves = curves.map((curve) => ({
    ...curve,
    visibleValues: curve.values.slice(viewStart, viewEnd + 1),
    visibleDates: curve.dates.slice(viewStart, viewEnd + 1),
  })).filter((curve) => curve.visibleValues.length);
  const allValues = visibleCurves.flatMap((row) => row.visibleValues);
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;
  const primaryDates = visibleCurves.find((curve) => curve.visibleDates.length)?.visibleDates || [];

  ctx.fillStyle = "rgba(237,244,248,.72)";
  ctx.textAlign = "right";
  for (let i = 0; i < 5; i += 1) {
    const ratio = i / 4;
    const value = max - range * ratio;
    const y = top + chartHeight * ratio + 4;
    ctx.fillText(money(value), left - 10, y);
  }

  visibleCurves.forEach((curve, curveIndex) => {
    ctx.beginPath();
    curve.visibleValues.forEach((value, index) => {
      const x = left + (index / Math.max(1, curve.visibleValues.length - 1)) * chartWidth;
      const y = top + chartHeight - ((value - min) / range) * chartHeight;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = colors[curveIndex % colors.length];
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.fillStyle = colors[curveIndex % colors.length];
    ctx.textAlign = "left";
    ctx.fillText(curve.name, left + 8 + curveIndex * 116, 20);
  });

  const tickCount = Math.min(9, Math.max(5, Math.floor(chartWidth / 150)));
  ctx.textAlign = "center";
  ctx.fillStyle = "rgba(237,244,248,.72)";
  for (let i = 0; i < tickCount; i += 1) {
    const ratio = i / Math.max(1, tickCount - 1);
    const x = left + ratio * chartWidth;
    const dateIndex = Math.round(ratio * Math.max(0, primaryDates.length - 1));
    const raw = primaryDates[dateIndex] || "";
    const label = primaryDates.length <= 420 ? raw : raw.length >= 7 ? raw.slice(0, 7) : raw;
    ctx.fillText(label, x, height - 22);
  }

  drawStrategyChartHover(ctx, visibleCurves, { left, top, chartWidth, chartHeight, min, range, height, colors });
  const firstDate = primaryDates[0] || "-";
  const lastDate = primaryDates[primaryDates.length - 1] || "-";
  updateChartViewportLabel(firstDate, lastDate, viewStart, viewEnd, totalPoints);
  if (legend) {
    legend.innerHTML = visibleCurves.map((curve, index) => `
      <div class="legend-chip" style="--series-color:${colors[index % colors.length]}">
        <i></i>
        <strong>${curve.name}</strong>
        <span>${escapeHtml(symbolSubLabel(symbolMeta(curve.symbol)))}</span>
        <b>${preset.name}</b>
        <em>전략 ${pct(curve.totalReturn)} / 보유 ${pct(curve.buyHoldReturn)}</em>
      </div>
    `).join("");
  }
}

function normalizeStrategyChartView(totalPoints, resetView = false) {
  const view = state.strategyChart;
  const minWindow = Math.min(totalPoints, 30);
  if (resetView || view.end === null || view.end >= totalPoints || view.start < 0) {
    const defaultWindow = Math.min(totalPoints, 520);
    view.end = totalPoints - 1;
    view.start = Math.max(0, totalPoints - defaultWindow);
  }
  let start = Math.floor(Number(view.start || 0));
  let end = Math.floor(Number(view.end ?? totalPoints - 1));
  if (end < start) [start, end] = [end, start];
  if (end - start + 1 < minWindow) end = Math.min(totalPoints - 1, start + minWindow - 1);
  if (end >= totalPoints) {
    const span = end - start;
    end = totalPoints - 1;
    start = Math.max(0, end - span);
  }
  start = Math.max(0, Math.min(start, Math.max(0, totalPoints - minWindow)));
  end = Math.max(start + minWindow - 1, Math.min(end, totalPoints - 1));
  view.start = start;
  view.end = end;
}

function updateChartViewportLabel(firstDate = "-", lastDate = "-", start = 0, end = 0, total = 0) {
  const node = el("#chartViewportLabel");
  if (!node) return;
  const bars = total ? `${Number(end - start + 1).toLocaleString()} / ${Number(total).toLocaleString()}개` : "대기";
  node.textContent = `${firstDate} ~ ${lastDate} · ${bars} · 휠 확대/축소, 드래그 좌우 이동`;
}

function drawStrategyChartHover(ctx, curves, box) {
  const hoverX = state.strategyChart.hoverX;
  if (hoverX === null || !Number.isFinite(hoverX) || !curves.length) return;
  const { left, top, chartWidth, chartHeight, colors } = box;
  const x = Math.max(left, Math.min(left + chartWidth, hoverX));
  const ratio = (x - left) / Math.max(1, chartWidth);
  const firstCurve = curves[0];
  const index = Math.max(0, Math.min(firstCurve.visibleValues.length - 1, Math.round(ratio * (firstCurve.visibleValues.length - 1))));
  const date = firstCurve.visibleDates[index] || "-";
  ctx.save();
  ctx.strokeStyle = "rgba(237,244,248,.36)";
  ctx.setLineDash([4, 5]);
  ctx.beginPath();
  ctx.moveTo(x, top);
  ctx.lineTo(x, top + chartHeight);
  ctx.stroke();
  ctx.setLineDash([]);
  const tooltipRows = curves.slice(0, 4).map((curve, curveIndex) => {
    const value = curve.visibleValues[Math.min(index, curve.visibleValues.length - 1)];
    return { name: curve.name, color: colors[curveIndex % colors.length], value };
  });
  const tooltipWidth = 230;
  const tooltipHeight = 34 + tooltipRows.length * 18;
  const tx = x > left + chartWidth - tooltipWidth - 16 ? x - tooltipWidth - 12 : x + 12;
  const ty = top + 10;
  ctx.fillStyle = "rgba(7, 11, 16, .92)";
  ctx.strokeStyle = "rgba(84, 215, 255, .42)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(tx, ty, tooltipWidth, tooltipHeight, 12);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#edf4f8";
  ctx.textAlign = "left";
  ctx.fillText(date, tx + 12, ty + 22);
  tooltipRows.forEach((row, rowIndex) => {
    ctx.fillStyle = row.color;
    ctx.fillText(`${row.name}  ${money(row.value)}`, tx + 12, ty + 44 + rowIndex * 18);
  });
  ctx.restore();
}

function chartTotalPoints() {
  return Math.max(0, ...((state.strategyChart.results || []).map((result) => (result.equity_curve || []).length)));
}

function setStrategyChartWindow(windowSize) {
  const total = chartTotalPoints();
  if (!total) return;
  if (windowSize === "all") {
    state.strategyChart.start = 0;
    state.strategyChart.end = total - 1;
  } else {
    const span = Math.min(total, Number(windowSize) || 260);
    state.strategyChart.start = Math.max(0, total - span);
    state.strategyChart.end = total - 1;
  }
  state.strategyChart.hoverX = null;
  drawCompareChart(null, false);
}

function zoomStrategyChart(direction, anchorRatio = 0.5) {
  const total = chartTotalPoints();
  if (!total) return;
  normalizeStrategyChartView(total, false);
  const view = state.strategyChart;
  const currentSpan = view.end - view.start + 1;
  const factor = direction < 0 ? 0.72 : 1.28;
  const nextSpan = Math.max(30, Math.min(total, Math.round(currentSpan * factor)));
  const anchor = view.start + anchorRatio * Math.max(1, currentSpan - 1);
  let start = Math.round(anchor - anchorRatio * Math.max(1, nextSpan - 1));
  let end = start + nextSpan - 1;
  if (start < 0) {
    end -= start;
    start = 0;
  }
  if (end >= total) {
    start -= end - total + 1;
    end = total - 1;
  }
  view.start = Math.max(0, start);
  view.end = Math.min(total - 1, end);
  drawCompareChart(null, false);
}

function panStrategyChart(deltaBars) {
  const total = chartTotalPoints();
  if (!total) return;
  normalizeStrategyChartView(total, false);
  const view = state.strategyChart;
  const span = view.end - view.start;
  let start = Math.round(view.start + deltaBars);
  let end = start + span;
  if (start < 0) {
    end -= start;
    start = 0;
  }
  if (end >= total) {
    start -= end - total + 1;
    end = total - 1;
  }
  view.start = Math.max(0, start);
  view.end = Math.min(total - 1, end);
  drawCompareChart(null, false);
}

function ensureStrategyChartControls() {
  const canvas = el("#strategyCompareChart");
  const panel = canvas?.closest(".research-chart-panel");
  if (!canvas || !panel || el("#strategyChartToolbar")) return;
  canvas.insertAdjacentHTML("beforebegin", `
    <div class="chart-toolbar" id="strategyChartToolbar">
      <div class="chart-buttons">
        <button data-chart-window="130">6개월</button>
        <button data-chart-window="260">1년</button>
        <button data-chart-window="780">3년</button>
        <button data-chart-window="all">전체</button>
        <button id="chartZoomIn">확대</button>
        <button id="chartZoomOut">축소</button>
        <button id="chartPanLeft">← 과거</button>
        <button id="chartPanRight">최근 →</button>
      </div>
      <span id="chartViewportLabel">차트 대기</span>
    </div>
  `);
  panel.querySelectorAll("[data-chart-window]").forEach((button) => {
    button.addEventListener("click", () => setStrategyChartWindow(button.dataset.chartWindow));
  });
  el("#chartZoomIn")?.addEventListener("click", () => zoomStrategyChart(-1));
  el("#chartZoomOut")?.addEventListener("click", () => zoomStrategyChart(1));
  el("#chartPanLeft")?.addEventListener("click", () => panStrategyChart(-Math.max(10, Math.round((state.strategyChart.end - state.strategyChart.start + 1) * 0.35))));
  el("#chartPanRight")?.addEventListener("click", () => panStrategyChart(Math.max(10, Math.round((state.strategyChart.end - state.strategyChart.start + 1) * 0.35))));
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const anchorRatio = (event.clientX - rect.left) / Math.max(1, rect.width);
    zoomStrategyChart(event.deltaY, Math.max(0, Math.min(1, anchorRatio)));
  }, { passive: false });
  canvas.addEventListener("pointerdown", (event) => {
    const view = state.strategyChart;
    view.dragging = true;
    view.dragStartX = event.clientX;
    view.dragStartStart = view.start;
    view.dragStartEnd = view.end ?? chartTotalPoints() - 1;
    canvas.setPointerCapture(event.pointerId);
    canvas.classList.add("dragging");
  });
  canvas.addEventListener("pointermove", (event) => {
    const rect = canvas.getBoundingClientRect();
    const view = state.strategyChart;
    view.hoverX = ((event.clientX - rect.left) / Math.max(1, rect.width)) * canvas.width;
    if (view.dragging) {
      const span = Math.max(1, view.dragStartEnd - view.dragStartStart + 1);
      const deltaBars = Math.round(-((event.clientX - view.dragStartX) / Math.max(1, rect.width)) * span);
      view.start = view.dragStartStart + deltaBars;
      view.end = view.dragStartEnd + deltaBars;
    }
    drawCompareChart(null, false);
  });
  canvas.addEventListener("pointerup", (event) => {
    state.strategyChart.dragging = false;
    canvas.classList.remove("dragging");
    try { canvas.releasePointerCapture(event.pointerId); } catch (_) {}
  });
  canvas.addEventListener("pointerleave", () => {
    state.strategyChart.hoverX = null;
    state.strategyChart.dragging = false;
    canvas.classList.remove("dragging");
    drawCompareChart(null, false);
  });
}

function renderTradeQuality(quality = {}) {
  setText("qualityWinRate", `${Number(quality.win_rate_pct || 0).toFixed(1)}%`);
  setText("qualityProfitFactor", Number(quality.profit_factor || 0).toFixed(2));
  setText("qualityExpectancy", pct(Number(quality.expectancy_pct || 0)));
  setText("qualitySqn", Number(quality.sqn || 0).toFixed(2));
  setText("qualityLossStreak", `${Number(quality.longest_loss_streak || 0)}회`);
}

function renderBacktestRiskGate(gate = {}) {
  const panel = el("#backtestGatePanel");
  if (!panel) return;
  const status = gate.status || "WAIT";
  panel.dataset.status = status;
  setText("backtestGateStatus", status === "PASSED" ? "실전 후보 가능" : status === "REVIEW" ? "추가 검토 필요" : status === "BLOCKED" ? "실전 후보 차단" : "위험 게이트 대기");
  setText("backtestGateMessage", gate.message || "백테스트 후 실전 후보 가능 여부를 표시합니다.");
  const checks = gate.checks || [];
  el("#backtestGateChecks").innerHTML = checks.length
    ? checks.map((check) => `
      <span class="${check.ok ? "passed" : "failed"}">
        ${check.ok ? "통과" : "차단"} · ${check.name}: ${Number(check.value || 0).toFixed(2)} / ${check.required}
      </span>
    `).join("")
    : `<span class="waiting">아직 판정 없음</span>`;
}

async function loadStatus() {
  const response = await fetch("/api/status");
  const status = await response.json();
  const present = status.projects.filter((project) => project.exists).length;
  setText("engineCount", `${present}/${status.projects.length}`);
}

function compactNumber(value, digits = 1) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) return "0";
  return number.toFixed(digits).replace(/\.0$/, "");
}

function formatUptime(seconds) {
  const total = Math.max(0, Number(seconds || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return `${hours}시간 ${minutes}분`;
  return `${minutes}분`;
}

function renderSystemResources(data = null) {
  const node = el("#suiteStatus");
  if (!node) return;
  if (!data) {
    node.className = "server-state resource-state";
    node.innerHTML = `
      <strong>PC 자원 확인</strong>
      <span>RAM - · 앱 -</span>
      <small>디스크 여유 확인 중</small>
    `;
    return;
  }
  const app = data.app || {};
  const system = data.system || {};
  const level = data.level || "ok";
  node.className = `server-state resource-state ${level}`;
  node.title = data.message || "시스템 자원 상태";
  node.innerHTML = `
    <strong>PC ${escapeHtml(data.label || "여유")}</strong>
    <span>RAM ${compactNumber(system.memory_used_pct, 0)}% · 앱 ${compactNumber(app.memory_mb, 0)}MB</span>
    <small>디스크 ${compactNumber(system.disk_free_gb, 1)}GB 여유 · CPU ${compactNumber(app.cpu_pct, 1)}% · ${formatUptime(app.uptime_seconds)}</small>
  `;
}

async function loadSystemResources() {
  try {
    const response = await fetch("/api/system/resources");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "시스템 자원 조회 실패");
    renderSystemResources(result);
  } catch (error) {
    const node = el("#suiteStatus");
    if (!node) return;
    node.className = "server-state resource-state warning";
    node.innerHTML = `
      <strong>PC 확인 필요</strong>
      <span>자원 조회 실패</span>
      <small>${escapeHtml(error.message || "다시 시도 중")}</small>
    `;
  }
}

async function loadIntegrations() {
  const response = await fetch("/api/integrations/status");
  const result = await response.json();
  state.integrations = result;
  const kisReady = Boolean(result.kis && result.kis.configured);
  const dartReady = Boolean(result.dart && result.dart.configured);
  const tossReady = Boolean(result.toss_public && result.toss_public.configured);
  const ecosReady = Boolean(result.ecos && result.ecos.configured);
  const fredReady = Boolean(result.fred && result.fred.configured);
  const liveOn = Boolean(result.safety && result.safety.live_trading);
  setText("kisStatus", kisReady ? t.apiReady : t.apiMissing);
  setText("kisMode", result.kis ? `${result.kis.mode}${result.kis.readonly ? " / RO" : ""}` : "-");
  setText("dartStatus", dartReady ? t.apiReady : t.apiMissing);
  setText("tossStatus", tossReady ? "읽기전용" : t.apiMissing);
  setText("ecosStatus", ecosReady ? t.apiReady : t.apiMissing);
  setText("fredStatus", fredReady ? t.apiReady : t.apiMissing);
  setText("liveTradingStatus", liveOn ? t.enabled : t.disabled);
  setText("apiSafetyStatus", t.apiLocked);
  setText("journalKisStatus", kisReady ? t.apiReady : t.apiMissing);
  setText("journalDartStatus", dartReady ? t.apiReady : t.apiMissing);
  setText("journalTossStatus", tossReady ? "읽기전용" : t.apiMissing);
  setText("journalEcosStatus", ecosReady ? t.apiReady : t.apiMissing);
  setText("journalFredStatus", fredReady ? t.apiReady : t.apiMissing);
  setText("journalSafetyStatus", liveOn ? t.enabled : t.apiLocked);
  if (el("#kisStatus")) el("#kisStatus").className = kisReady ? "up" : "flat";
  if (el("#dartStatus")) el("#dartStatus").className = dartReady ? "up" : "flat";
  if (el("#tossStatus")) el("#tossStatus").className = tossReady ? "up" : "flat";
  if (el("#ecosStatus")) el("#ecosStatus").className = ecosReady ? "up" : "flat";
  if (el("#fredStatus")) el("#fredStatus").className = fredReady ? "up" : "flat";
  if (el("#liveTradingStatus")) el("#liveTradingStatus").className = liveOn ? "down" : "up";
  if (el("#journalEcosStatus")) el("#journalEcosStatus").className = ecosReady ? "up" : "flat";
  if (el("#journalFredStatus")) el("#journalFredStatus").className = fredReady ? "up" : "flat";
  if (el("#journalTossStatus")) el("#journalTossStatus").className = tossReady ? "up" : "flat";
  await loadDartDisclosures();
  await loadKisWatch();
  await loadKisAccount();
  await loadLivePerformance();
  await loadMacroSnapshot(ecosReady || fredReady);
}

function renderFriendReleaseReadiness(data) {
  const summary = data.summary || {};
  const checks = Array.isArray(data.checks) ? data.checks : [];
  const envKeys = Array.isArray(data.env_keys) ? data.env_keys : [];
  const readyClass = data.ready ? "pass" : summary.blockers ? "blocker" : "warning";
  const checkedAt = new Date().toLocaleString("ko-KR", { hour12: false });
  state.friendReleaseCheckedAtMs = Date.now();
  state.friendReleaseCheckedAt = checkedAt;
  setText("friendReleaseScore", `${Math.round(Number(data.score || 0))}점`);
  setText("friendReleaseStatus", data.status || "점검 필요");
  setText("friendReleasePrivateCount", `${Number(summary.repo_private_files ?? summary.private_files ?? 0) + Number(summary.dist_private_files ?? 0)}개`);
  setText("friendReleaseRuntimeCount", `${summary.runtime_private_files ?? 0}개`);
  setText("friendReleaseEnvCount", `${envKeys.filter((item) => item.present_in_example).length}/${envKeys.length || 0}`);
  setText("friendReleaseDistState", summary.dist_exists ? "있음" : "없음");
  setText("friendReleaseCheckedAt", checkedAt.replace(/^\d{4}\.\s*/, ""));
  setText("friendReleaseCommand", data.release_command || ".\\prepare_friend_release.ps1");
  updateFriendReleaseCommandGate(data);
  ["friendReleaseScore", "friendReleaseStatus"].forEach((id) => {
    const node = el(`#${id}`);
    if (node) node.className = readyClass;
  });

  const list = el("#friendReleaseChecks");
  if (!list) return;
  const labelMap = { pass: "통과", warning: "주의", blocker: "차단" };
  list.innerHTML = checks.map((item) => {
    const status = item.status || "warning";
    const action = item.action ? `<small>${escapeHtml(item.action)}</small>` : "";
    const path = item.path ? `<code>${escapeHtml(item.path)}</code>` : "";
    return `
      <article class="release-check ${escapeHtml(status)}">
        <div>
          <strong>${escapeHtml(item.label || "점검 항목")}</strong>
          <span>${escapeHtml(labelMap[status] || status)}</span>
        </div>
        <p>${escapeHtml(item.detail || "")}</p>
        ${path}
        ${action}
      </article>
    `;
  }).join("");
}

function updateFriendReleaseCommandGate(data = null) {
  const button = el("#copyFriendReleaseCommand");
  if (!button) return;
  const hasResult = Boolean(data);
  const ready = Boolean(data?.ready);
  const checks = Array.isArray(data?.checks) ? data.checks : [];
  const blockerChecks = checks.filter((item) => item.status === "blocker");
  const warningChecks = checks.filter((item) => item.status === "warning");
  const blockerCount = blockerChecks.length;
  const warningCount = warningChecks.length;
  const firstFix = blockerChecks[0] || warningChecks[0] || null;
  const firstFixLabel = firstFix
    ? `${firstFix.label || "점검 항목"}${firstFix.action ? ` · ${firstFix.action}` : ""}`
    : "";
  button.disabled = hasResult && !ready;
  button.classList.toggle("locked", hasResult && !ready);
  button.textContent = hasResult && !ready ? "복사 잠금" : "명령 복사";
  button.title = hasResult && !ready
    ? "차단/주의 항목을 해결한 뒤 다시 점검해야 패키지 생성 명령을 복사할 수 있습니다."
    : "친구 배포 준비도가 통과된 경우에만 패키지 생성 명령을 복사합니다.";
  button.dataset.buttonHelpManaged = "1";
  if (!hasResult) {
    setFriendReleaseCommandState("점검 후 명령 복사 가능", "info");
  } else if (ready) {
    setFriendReleaseCommandState("명령 복사 가능", "success");
  } else {
    setFriendReleaseCommandState(`복사 잠금 · 차단 ${blockerCount} / 주의 ${warningCount}${firstFixLabel ? ` · 먼저 ${firstFixLabel}` : ""}`, blockerCount ? "danger" : "warning");
  }
}

async function loadFriendReleaseReadiness() {
  try {
    const response = await fetch("/api/friend-release/readiness");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "친구 배포 준비도 점검 실패");
    state.friendReleaseReadiness = result;
    renderFriendReleaseReadiness(result);
  } catch (error) {
    setText("friendReleaseStatus", error.message || "점검 실패");
    const failedAt = new Date().toLocaleString("ko-KR", { hour12: false });
    state.friendReleaseCheckedAtMs = Date.now();
    state.friendReleaseCheckedAt = `${failedAt} 실패`;
    setText("friendReleaseCheckedAt", "실패");
    updateFriendReleaseCommandGate({ ready: false });
    setFriendReleaseCommandState("점검 실패 · 다시 시도 필요", "danger");
    const list = el("#friendReleaseChecks");
    if (list) {
      list.innerHTML = `
        <article class="release-check blocker">
          <div><strong>점검 실패</strong><span>차단</span></div>
          <p>${escapeHtml(error.message || "다시 시도해주세요.")}</p>
        </article>
      `;
    }
  }
}

const ACCOUNT_COLORS = ["#54d7ff", "#59d6a3", "#ffcf5c", "#ff6973", "#b88cff", "#71a7ff", "#f28c38", "#9be15d"];

function formatKrw(value) {
  return `${money0(Number(value || 0))}원`;
}

function formatSignedKrw(value) {
  const number = Number(value || 0);
  const sign = number > 0 ? "+" : number < 0 ? "-" : "";
  return `${sign}${money0(Math.abs(number))}원`;
}

function formatDateTimeShort(value) {
  if (!value) return "기록 없음";
  try {
    return new Date(String(value)).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
  } catch (_) {
    return String(value);
  }
}

function formatMinutesRemaining(value) {
  if (value === null || value === undefined || value === "") return "남은 시간 대기";
  const raw = Number(value);
  if (!Number.isFinite(raw)) return "남은 시간 대기";
  const minutes = Math.max(0, Math.round(raw));
  if (minutes < 60) return `${minutes}분 남음`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours < 24) return rest ? `약 ${hours}시간 ${rest}분 남음` : `약 ${hours}시간 남음`;
  const days = Math.floor(hours / 24);
  const dayHours = hours % 24;
  return dayHours ? `약 ${days}일 ${dayHours}시간 남음` : `약 ${days}일 남음`;
}

function formatEventCountdown(eventAt, fallbackMinutes = null) {
  if (eventAt) {
    const eventTime = new Date(String(eventAt)).getTime();
    if (Number.isFinite(eventTime)) {
      return formatMinutesRemaining((eventTime - Date.now()) / 60000);
    }
  }
  return formatMinutesRemaining(fallbackMinutes);
}

function pilotStepStatusLabel(value) {
  const key = String(value || "").toLowerCase();
  return {
    active: "진행",
    approved: "승인",
    blocked: "차단",
    done: "완료",
    locked: "잠금",
    ok: "정상",
    pending: "대기",
    ready: "준비",
    wait: "대기",
    warning: "주의",
  }[key] || value || "-";
}

function realExecutionLabel(value) {
  const key = String(value || "").toUpperCase();
  return {
    APPROVAL_REQUIRED: "승인 필요",
    BLOCKED: "잠금",
    DELEGATED_LIVE_OFF: "위임 실전 꺼짐",
    DELEGATED_LIVE_ON: "위임 실전 켜짐",
    LIVE_READY_NOT_SUBMITTED: "Dry 통과",
    LIVE_SUBMITTED: "전송됨",
    READY_TO_SUBMIT: "전송 가능",
  }[key] || value || "잠금";
}

function koreanStatusText(value) {
  return String(value || "")
    .replaceAll("READY_TO_SUBMIT", "전송 가능")
    .replaceAll("APPROVAL_REQUIRED", "승인 필요")
    .replaceAll("DELEGATED_LIVE_ON", "위임 실전 켜짐")
    .replaceAll("DELEGATED_LIVE_OFF", "위임 실전 꺼짐")
    .replaceAll("LIVE_READY_NOT_SUBMITTED", "Dry 통과")
    .replaceAll("LIVE_SUBMITTED", "전송됨")
    .replaceAll("BLOCKED", "잠금")
    .replaceAll("READY", "준비")
    .replaceAll("BLOCK", "차단");
}

function formatRelativeAge(value) {
  if (!value) return "생성시각 대기";
  const time = new Date(String(value)).getTime();
  if (!Number.isFinite(time)) return "생성시각 확인 불가";
  const minutes = Math.max(0, Math.floor((Date.now() - time) / 60000));
  if (minutes < 1) return "방금 생성";
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours < 24) return rest ? `${hours}시간 ${rest}분 전` : `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

function smallAccountFreshness(value) {
  if (!value) return { label: "생성 대기", level: "stale" };
  const time = new Date(String(value)).getTime();
  if (!Number.isFinite(time)) return { label: "시각 오류", level: "stale" };
  const minutes = Math.max(0, Math.floor((Date.now() - time) / 60000));
  if (minutes < 5) return { label: "판단 최신", level: "fresh" };
  if (minutes < 30) return { label: "관찰 가능", level: "ok" };
  if (minutes < 60) return { label: "재확인 권장", level: "warn" };
  return { label: "오래됨", level: "stale" };
}

function isSmallAccountRefreshPinned(node) {
  if (!node) return false;
  if (node.dataset.status === "running") return true;
  const pinnedUntil = Number(node.dataset.pinnedUntil || 0);
  if (node.dataset.pinned === "manual" && pinnedUntil > Date.now()) return true;
  if (node.dataset.pinned === "manual") {
    delete node.dataset.pinned;
    delete node.dataset.pinnedUntil;
  }
  return false;
}

function setSmallAccountRefreshStatus(status, message, ttlMs = 120000) {
  const node = el("#smallAccountRefreshStatus");
  if (!node) return;
  node.dataset.pinned = "manual";
  node.dataset.pinnedUntil = String(Date.now() + ttlMs);
  node.dataset.status = status;
  node.textContent = message;
}

function updateSmallAccountCountdowns() {
  document.querySelectorAll("[data-countdown-at]").forEach((node) => {
    node.textContent = formatEventCountdown(node.dataset.countdownAt, node.dataset.countdownMinutes);
  });
  document.querySelectorAll("[data-relative-age-at]").forEach((node) => {
    node.textContent = formatRelativeAge(node.dataset.relativeAgeAt);
  });
  document.querySelectorAll("[data-freshness-at]").forEach((node) => {
    const freshness = smallAccountFreshness(node.dataset.freshnessAt);
    node.textContent = freshness.label;
    node.dataset.freshnessLevel = freshness.level;
  });
  const refreshStatusNode = el("#smallAccountRefreshStatus");
  isSmallAccountRefreshPinned(refreshStatusNode);
}

function latestTicketForSymbol(symbol, mode = "paper") {
  const normalized = normalizeSymbol(symbol);
  const tickets = state.lastOpsStatus?.paper?.recent_tickets || [];
  return tickets.find((ticket) => normalizeSymbol(ticket.symbol) === normalized && String(ticket.mode || "") === mode && String(ticket.side || "").toUpperCase() === "BUY")
    || tickets.find((ticket) => normalizeSymbol(ticket.symbol) === normalized && String(ticket.side || "").toUpperCase() === "BUY")
    || null;
}

function accountExitMemo(position, mode) {
  if (mode === "live") {
    return "실계좌는 현재 읽기전용입니다. 매도 계획은 AI 후보/사용자 메모와 연결되면 여기에 표시됩니다.";
  }
  const pnl = Number(position.pnlPct || 0);
  if (pnl <= -3) return "손실 구간: 손절 기준, 뉴스 변화, 전략 훼손 여부를 우선 복기합니다.";
  if (pnl >= 8) return "수익 구간: 추세 훼손, 목표가 도달, 부분청산 필요 여부를 다음 점검에서 확인합니다.";
  return "보유 관찰: 다음 자동 점검에서 뉴스/공시/백테스트 조건이 유지되는지 확인합니다.";
}

function normalizePaperAccount() {
  const paper = state.lastOpsStatus?.paper || {};
  const positions = Array.isArray(paper.positions) ? paper.positions : [];
  const valuation = paper.valuation_guard || {};
  const valuationQuality = String(paper.valuation_quality || valuation.quality || "ok");
  const valuationWarning = valuationQuality === "suspect"
    ? `Paper 가격/통화 보정 ${Number(valuation.warning_count || 0)}건`
    : valuationQuality === "watch"
      ? `Paper 가격/통화 확인 필요 ${Number(valuation.warning_count || 0)}건`
      : "";
  return {
    mode: "paper",
    label: "모의투자 계좌",
    badge: "Paper 운용",
    ok: Boolean(state.lastOpsStatus),
    account: "OPS 모의 장부",
    cash: Number(paper.cash || 0),
    stockValue: Number(paper.market_value || 0),
    equity: Number(paper.equity || 0),
    pnl: Number(paper.total_pnl || 0),
    pnlPct: Number(paper.total_pnl_pct || 0),
    updatedAt: state.lastOpsStatus?.generated_at || "",
    safety: valuationWarning || state.lastOpsStatus?.safety || "모의 장부 조회 대기",
    valuationQuality,
    valuationGuard: valuation,
    positions: positions.map((row) => {
      const meta = symbolMeta(row.symbol, row);
      const ticket = latestTicketForSymbol(row.symbol, "paper");
      const value = Number(row.value || 0);
      const equity = Number(paper.equity || 0);
      return {
        symbol: meta.symbol,
        name: meta.name,
        quantity: Number(row.quantity || 0),
        avgPrice: Number(row.avg_cost || 0),
        currentPrice: Number(row.mark || 0),
        rawPrice: Number(row.raw_mark || row.mark || 0),
        value,
        weight: equity > 0 ? (value / equity) * 100 : 0,
        pnl: Number(row.unrealized_pnl || 0),
        pnlPct: Number(row.unrealized_pct || 0),
        boughtAt: ticket?.created_at || "",
        why: ticket?.memo || ticket?.source || "매수 메모가 아직 연결되지 않았습니다.",
        source: ticket?.source || "-",
        exitPlan: accountExitMemo({ pnlPct: Number(row.unrealized_pct || 0) }, "paper"),
        valuationQuality: String(row.valuation_quality || "ok"),
        valuationGuard: row.valuation_guard || {},
      };
    }),
  };
}

function normalizeLiveAccount() {
  const account = state.liveAccountSnapshot || {};
  const summary = account.summary || {};
  const positions = Array.isArray(account.positions) ? account.positions : [];
  const cash = Number(summary.available_cash || summary.cash || 0);
  const stockValue = Number(summary.stock_value || 0);
  const equity = Number(summary.net_liquidation_value || summary.total_value || (cash + stockValue));
  const depositCash = Number(summary.deposit_cash || summary.settlement_cash || 0);
  return {
    mode: "live",
    label: "실투자 계좌",
    badge: account.readonly ? "KIS 읽기전용" : "KIS",
    ok: Boolean(account.ok),
    account: account.account_masked || "-",
    cash,
    stockValue,
    equity,
    pnl: Number(summary.profit_loss || 0),
    pnlPct: Number(summary.profit_loss_rate || 0),
    updatedAt: account.generated_at || "",
    safety: depositCash && Math.abs(depositCash - cash) > 1
      ? `주문가능 현금 기준 · 예수금 ${formatKrw(depositCash)}`
      : (account.safety || "실계좌는 조회 전용입니다."),
    positions: positions.map((row) => {
      const meta = symbolMeta(row.symbol, row);
      const value = Number(row.evaluation_amount || row.value || 0);
      return {
        symbol: meta.symbol,
        name: meta.name,
        quantity: Number(row.quantity || 0),
        avgPrice: Number(row.avg_price || 0),
        currentPrice: Number(row.current_price || 0),
        value,
        weight: equity > 0 ? (value / equity) * 100 : 0,
        pnl: Number(row.profit_loss || 0),
        pnlPct: Number(row.profit_loss_rate || 0),
        boughtAt: "",
        why: "KIS 잔고 조회에는 매수 사유 메모가 포함되지 않습니다. 주문/메모 연결 후 표시됩니다.",
        source: "KIS 잔고",
        exitPlan: accountExitMemo({}, "live"),
      };
    }),
  };
}

function activeAccountSnapshot() {
  return state.accountView === "live" ? normalizeLiveAccount() : normalizePaperAccount();
}

function accountSegments(account) {
  const equity = Number(account.equity || account.cash + account.stockValue || 0);
  const segments = (account.positions || [])
    .filter((item) => Number(item.value || 0) > 0)
    .map((item) => ({
      label: item.name || item.symbol,
      symbol: item.symbol,
      value: Number(item.value || 0),
      pct: equity > 0 ? (Number(item.value || 0) / equity) * 100 : 0,
    }));
  const cash = Number(account.cash || 0);
  if (cash > 0 || !segments.length) {
    segments.push({ label: "현금", symbol: "CASH", value: cash || equity, pct: equity > 0 ? ((cash || equity) / equity) * 100 : 100 });
  }
  return segments;
}

function conicGradientForSegments(segments) {
  if (!segments.length) return "rgba(128,151,168,.35) 0% 100%";
  let cursor = 0;
  const parts = segments.map((segment, index) => {
    const size = Math.max(0, Number(segment.pct || 0));
    const start = cursor;
    const end = Math.min(100, cursor + size);
    cursor = end;
    return `${ACCOUNT_COLORS[index % ACCOUNT_COLORS.length]} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
  });
  if (cursor < 100) parts.push(`rgba(128,151,168,.22) ${cursor.toFixed(2)}% 100%`);
  return parts.join(", ");
}

function renderAccountDashboard() {
  const root = el("#accountPositionRows");
  if (!root) return;
  const account = activeAccountSnapshot();
  const segments = accountSegments(account);
  document.querySelectorAll("[data-account-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.accountTab === state.accountView);
  });
  setText("accountDashboardState", `${account.badge} · ${account.ok ? "조회됨" : "대기"}`);
  setText("accountViewLabel", `${account.label} · ${account.account}`);
  setText("accountTotalValue", formatKrw(account.equity));
  setText("accountSubValue", `${formatDateTimeShort(account.updatedAt)} · ${account.safety}`);
  setText("accountCashValue", formatKrw(account.cash));
  setText("accountStockValue", formatKrw(account.stockValue));
  setText("accountPnlValue", `${formatKrw(account.pnl)} / ${pct(account.pnlPct)}`);
  setText("accountPositionCount", `${account.positions.length}개 보유`);
  setText("dashEquity", formatKrw(account.equity));
  setText("dashEquityHint", `${account.label} 기준`);
  setText("dashReturn", pct(account.pnlPct));
  setText("dashReturnHint", account.mode === "live" ? "실계좌 평가손익" : "모의계좌 총손익");
  const donut = el("#accountDonut");
  if (donut) donut.style.setProperty("--account-allocation", conicGradientForSegments(segments));
  setText("accountDonutCenter", account.positions.length ? `${account.positions.length}종목` : "현금");
  const legend = el("#accountLegend");
  if (legend) {
    legend.innerHTML = segments.map((segment, index) => `
      <div><i style="background:${ACCOUNT_COLORS[index % ACCOUNT_COLORS.length]}"></i><span>${escapeHtml(segment.label)}</span><b>${Number(segment.pct || 0).toFixed(1)}%</b></div>
    `).join("");
  }
  root.innerHTML = account.positions.length
    ? account.positions.map((position, index) => `
      <article class="account-position-card">
        <div class="account-position-top">
          <i style="background:${ACCOUNT_COLORS[index % ACCOUNT_COLORS.length]}"></i>
          <strong>${escapeHtml(position.name)}</strong>
          <span>${Number(position.weight || 0).toFixed(1)}%</span>
        </div>
        <div class="account-position-metrics">
          <div><b>${escapeHtml(position.name)}</b><small>종목명</small></div>
          <div><b>${Number(position.quantity || 0).toLocaleString()}</b><small>수량</small></div>
          <div><b>${formatKrw(position.value)}</b><small>평가금</small></div>
          <div><b class="${Number(position.pnlPct || 0) >= 0 ? "up" : "down"}">${pct(position.pnlPct || 0)}</b><small>손익률</small></div>
        </div>
        ${position.valuationQuality && position.valuationQuality !== "ok" ? `<div class="account-position-note"><b>가격 검문</b><span>${escapeHtml((position.valuationGuard?.warnings || []).join(", ") || position.valuationQuality)} · 원시가 ${formatKrw(position.rawPrice || 0)}</span></div>` : ""}
        <div class="account-position-note"><b>언제 샀나</b><span>${formatDateTimeShort(position.boughtAt)} · 평균 ${formatKrw(position.avgPrice)}</span></div>
        <div class="account-position-note"><b>왜 샀나</b><span>${escapeHtml(position.why)}</span></div>
        <div class="account-position-note"><b>언제 팔건가</b><span>${escapeHtml(position.exitPlan)}</span></div>
      </article>
    `).join("")
    : `<article class="account-position-empty"><strong>보유 종목 없음</strong><span>${account.mode === "live" ? "실계좌는 현재 현금만 확인됩니다." : "모의계좌 보유 종목이 없습니다."}</span></article>`;
}

function liveExitPlanSnippet(item = {}) {
  const symbol = normalizeSymbol(item.symbol || "");
  const cached = state.liveExitPlans.get(symbol) || null;
  const target = cached?.target && typeof cached.target === "object" ? cached.target : {};
  const loading = state.liveExitPlanLoading.has(symbol);
  const buyPrice = Number(target.avg_price || item.buy_price || 0);
  const currentPrice = Number(target.current_price || 0);
  const stopPrice = Number(target.stop_price || (buyPrice ? buyPrice * 0.98 : 0));
  const takeProfitPrice = Number(target.take_profit_price || (buyPrice ? buyPrice * 1.03 : 0));
  const pnlPct = Number(target.pnl_pct ?? (currentPrice && buyPrice ? ((currentPrice / buyPrice) - 1) * 100 : 0));
  const decision = String(target.decision || "").toUpperCase();
  const verdict = loading
    ? "확인 중"
    : decision === "SELL"
      ? "매도 후보"
      : decision === "HOLD"
        ? "보유 유지"
        : "라인 대기";
  const verdictClass = decision === "SELL" ? "sell" : decision === "HOLD" ? "hold" : "wait";
  const reason = String(target.reason || (cached?.error ? `조회 실패: ${cached.error}` : "버튼을 누르면 계좌 현재가 기준으로 다시 판단합니다."));
  const currentLine = currentPrice
    ? `<small>현재가 ${formatKrw(currentPrice)} · 손익률 ${pct(pnlPct)}</small>`
    : `<small>현재가는 버튼을 눌러 최신 계좌 기준으로 확인합니다.</small>`;
  return `
    <div class="live-exit-plan ${verdictClass}">
      <div class="live-exit-plan-top">
        <strong>매도계획</strong>
        <b>${escapeHtml(verdict)}</b>
      </div>
      <p>손절 ${formatKrw(stopPrice)} · 수익보호 ${formatKrw(takeProfitPrice)}</p>
      ${currentLine}
      <span>${escapeHtml(reason)}</span>
      <button type="button" data-live-exit-plan="${escapeHtml(symbol)}">${loading ? "확인 중..." : "매도계획 확인"}</button>
    </div>
  `;
}

async function loadLiveExitPlan(symbol, options = {}) {
  const normalized = normalizeSymbol(symbol || "");
  if (!normalized || state.liveExitPlanLoading.has(normalized)) return null;
  state.liveExitPlanLoading.add(normalized);
  const silent = Boolean(options.silent);
  const record = options.record !== false;
  if (!silent) renderLivePerformance();
  try {
    const response = await fetch(`/api/ops/live-exit-plan?symbol=${encodeURIComponent(normalized)}&record=${record ? "1" : "0"}`);
    const result = await response.json();
    state.liveExitPlans.set(normalized, result);
    state.liveExitPlanFetchedAt.set(normalized, Date.now());
    const target = result.target || {};
    if (!silent) addLog(`매도계획 확인: ${symbolDisplayName(normalized, target)} · ${target.decision || "-"} · ${pct(target.pnl_pct || 0)}`);
    return result;
  } catch (error) {
    state.liveExitPlans.set(normalized, { ok: false, error: error.message, target: { symbol: normalized } });
    state.liveExitPlanFetchedAt.set(normalized, Date.now());
    if (!silent) addLog(`매도계획 확인 실패: ${normalized} · ${error.message}`);
    return null;
  } finally {
    state.liveExitPlanLoading.delete(normalized);
    renderLivePerformance();
  }
}

function refreshLiveExitPlansForOpenLots(openLots = []) {
  const now = Date.now();
  openLots.slice(0, 6).forEach((item) => {
    const symbol = normalizeSymbol(item.symbol || "");
    if (!symbol || state.liveExitPlanLoading.has(symbol)) return;
    const fetchedAt = Number(state.liveExitPlanFetchedAt.get(symbol) || 0);
    if (now - fetchedAt < 90000) return;
    loadLiveExitPlan(symbol, { silent: true, record: false });
  });
}

function handleLiveExitPlanClick(event) {
  const exitPlanButton = event.target.closest("[data-live-exit-plan]");
  if (!exitPlanButton) return;
  event.preventDefault();
  event.stopPropagation();
  loadLiveExitPlan(exitPlanButton.dataset.liveExitPlan);
}

document.addEventListener("click", handleLiveExitPlanClick, true);

function livePerformanceDateKey(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const match = text.match(/20\d{2}-\d{2}-\d{2}/);
  if (match) return match[0];
  try {
    return new Date(text).toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
  } catch (_) {
    return "";
  }
}

function livePerformanceMatchesDate(item = {}, date = "") {
  if (!date) return true;
  return [item.buy_at, item.sell_at, item.created_at, item.submitted_at]
    .some((value) => livePerformanceDateKey(value) === date);
}

function livePerformanceSortKey(item = {}) {
  return String(item.sell_at || item.buy_at || item.created_at || item.submitted_at || "");
}

function renderLivePerformancePagination(total, page, pages) {
  const node = el("#livePerformancePagination");
  const info = el("#livePerformancePageInfo");
  if (info) {
    const filterLabel = state.livePerformanceDateFilter ? `${state.livePerformanceDateFilter} 매매` : "전체 매매";
    info.textContent = `${filterLabel} · ${Number(total).toLocaleString()}개 · ${page}/${pages}`;
  }
  if (!node) return;
  if (pages <= 1) {
    node.innerHTML = "";
    return;
  }
  const buttons = [];
  buttons.push(`<button type="button" data-live-performance-page="${Math.max(1, page - 1)}" ${page <= 1 ? "disabled" : ""}>이전</button>`);
  for (let index = 1; index <= pages; index += 1) {
    buttons.push(`<button type="button" data-live-performance-page="${index}" class="${index === page ? "active" : ""}">${index}</button>`);
  }
  buttons.push(`<button type="button" data-live-performance-page="${Math.min(pages, page + 1)}" ${page >= pages ? "disabled" : ""}>다음</button>`);
  node.innerHTML = buttons.join("");
}

function setLivePerformancePage(page) {
  const safePage = Math.max(1, Number(page || 1));
  state.livePerformancePage = safePage;
  renderLivePerformance();
}

function setLivePerformanceDateFilter(value = "") {
  state.livePerformanceDateFilter = String(value || "").slice(0, 10);
  state.livePerformancePage = 1;
  const input = el("#livePerformanceDateFilter");
  if (input && input.value !== state.livePerformanceDateFilter) input.value = state.livePerformanceDateFilter;
  renderLivePerformance();
}

function renderLivePerformanceTradeCard(item = {}) {
  const isOpen = item._kind === "open";
  const pnl = Number(item.pnl || 0);
  const title = escapeHtml(item.name || item.symbol || "종목");
  const tradeLine = isOpen
    ? `매수 ${formatDateTimeShort(item.buy_at)} @ ${formatKrw(item.buy_price)} · ${Number(item.quantity || 0).toLocaleString()}주`
    : `매수 ${formatDateTimeShort(item.buy_at)} @ ${formatKrw(item.buy_price)} → 매도 ${formatDateTimeShort(item.sell_at)} @ ${formatKrw(item.sell_price)}`;
  const resultLine = isOpen
    ? `${formatKrw(item.notional || 0)} 보유중`
    : `${formatSignedKrw(pnl)} / ${pct(item.pnl_pct)}`;
  const resultClass = isOpen ? "" : pnl >= 0 ? "up" : "down";
  const quality = item.buy_reason_quality || {};
  const qualityText = quality.grade ? `${quality.grade} · ${quality.message || ""}` : "미평가";
  const correctionNote = item.corrected
    ? `<em>계좌확인</em><span>확정 ${pct(item.pnl_pct)} · 제출가 원계산 ${pct(item.raw_pnl_pct)}</span>`
    : "";
  return `
    <article class="live-performance-row horizontal ${isOpen ? "open" : "closed"}">
      <div class="live-performance-main">
        <small class="live-performance-badge">${isOpen ? "보유중" : "정산 완료"}</small>
        <strong>${title}</strong>
        <span class="${resultClass}">${escapeHtml(resultLine)}</span>
      </div>
      <div class="live-performance-trade-line">
        <b>매매</b>
        <p>${escapeHtml(tradeLine)}</p>
        <small>${Number(item.quantity || 0).toLocaleString()}주 · ${isOpen ? "실시간 평가는 실계좌 패널 확인" : "제출 로그 FIFO 기준"}</small>
      </div>
      <div class="live-performance-reasons">
        <em>테마</em><span>${escapeHtml(item.theme || "테마 확인 필요")} · ${escapeHtml(item.theme_detail || "리서치 보강 필요")}</span>
        <em>매수 근거</em><span>${escapeHtml(item.buy_reason || "기록 없음")}</span>
        <em>근거 품질</em><span class="reason-quality ${escapeHtml(quality.level || "unknown")}">${escapeHtml(qualityText)}</span>
        <em>${isOpen ? "현재 상태" : "매도 근거"}</em><span>${escapeHtml(isOpen ? "매도계획 버튼을 누르면 계좌 현재가 기준으로 판단합니다." : item.sell_reason || "기록 없음")}</span>
        ${correctionNote}
      </div>
      <div class="live-performance-meta">
        ${isOpen ? liveExitPlanSnippet(item) : ""}
        <small>기준일 ${escapeHtml(livePerformanceDateKey(item.sell_at || item.buy_at) || "-")}</small>
      </div>
    </article>
  `;
}

function renderLivePerformance(performance = state.livePerformance) {
  const rowsNode = el("#livePerformanceRows");
  const dailyNode = el("#livePerformanceDailyRows");
  const reviewNode = el("#liveTradeReviewRows");
  if (!rowsNode) return;
  if (!performance) {
    setText("livePerformanceState", "조회 대기");
    rowsNode.innerHTML = `<article class="live-performance-empty">실전 주문 로그를 확인하는 중입니다.</article>`;
    if (dailyNode) dailyNode.innerHTML = "";
    if (reviewNode) reviewNode.innerHTML = "";
    return;
  }
  state.livePerformance = performance;
  const realized = Array.isArray(performance.realized) ? performance.realized : [];
  const openLots = Array.isArray(performance.open_lots) ? performance.open_lots : [];
  refreshLiveExitPlansForOpenLots(openLots);
  const latest = performance.latest_realized || null;
  const realizedPnl = Number(performance.realized_gross_pnl || 0);
  const realizedNode = el("#livePerfRealized");
  if (realizedNode) {
    realizedNode.textContent = formatSignedKrw(realizedPnl);
    realizedNode.className = realizedPnl >= 0 ? "up" : "down";
  }
  const todayPnl = Number(performance.today_realized_gross_pnl || 0);
  const todayNode = el("#livePerfToday");
  if (todayNode) {
    todayNode.textContent = formatSignedKrw(todayPnl);
    todayNode.className = todayPnl >= 0 ? "up" : "down";
  }
  setText("livePerformanceState", performance.ok ? `오늘 ${performance.today_realized_count || 0}건 · 전체 ${performance.realized_count || 0}건` : "조회 실패");
  setText(
    "livePerfLatest",
    latest
      ? `${latest.name || latest.symbol || "종목"} ${formatSignedKrw(latest.pnl)} (${pct(latest.pnl_pct)}${latest.corrected ? ` · 계좌확인 / 제출가 ${pct(latest.raw_pnl_pct)}` : ""})`
      : "매도 없음",
  );
  setText("livePerfOpen", `${openLots.length}개 열림`);
  setText("livePerfWinRate", `${Number(performance.win_rate || 0).toFixed(1)}%`);
  const qualitySummary = performance.reason_quality_summary || {};
  const qualityNode = el("#livePerfReasonQuality");
  if (qualityNode) {
    const total = Number(qualitySummary.total || 0);
    const high = Number(qualitySummary.high || 0);
    const low = Number(qualitySummary.low || 0) + Number(qualitySummary.unknown || 0);
    qualityNode.textContent = total ? `높음 ${high}/${total} · 낮음 ${low}` : "대기";
    qualityNode.className = low > 0 ? "down" : total && high === total ? "up" : "flat";
    qualityNode.title = qualitySummary.next_action || "";
  }
  setText("livePerformanceSafety", performance.safety || "수수료/세금 반영 전입니다.");
  const reasonQualityText = (item = {}) => {
    const quality = item.buy_reason_quality || {};
    return quality.grade ? `${quality.grade} · ${quality.message || ""}` : "미평가";
  };
  if (el("#livePerformanceDateFilter") && el("#livePerformanceDateFilter").value !== state.livePerformanceDateFilter) {
    el("#livePerformanceDateFilter").value = state.livePerformanceDateFilter;
  }
  const tradeItems = [
    ...openLots.map((item) => ({ ...item, _kind: "open" })),
    ...realized.map((item) => ({ ...item, _kind: "closed" })),
  ]
    .filter((item) => livePerformanceMatchesDate(item, state.livePerformanceDateFilter))
    .sort((left, right) => livePerformanceSortKey(right).localeCompare(livePerformanceSortKey(left)));
  const pageSize = Math.max(1, Number(state.livePerformancePageSize || 4));
  const totalPages = Math.max(1, Math.ceil(tradeItems.length / pageSize));
  const currentPage = Math.min(Math.max(1, Number(state.livePerformancePage || 1)), totalPages);
  state.livePerformancePage = currentPage;
  const startIndex = (currentPage - 1) * pageSize;
  const pageItems = tradeItems.slice(startIndex, startIndex + pageSize);
  renderLivePerformancePagination(tradeItems.length, currentPage, totalPages);
  rowsNode.innerHTML = pageItems.length
    ? pageItems.map((item) => renderLivePerformanceTradeCard(item)).join("")
    : `<article class="live-performance-empty">${state.livePerformanceDateFilter ? `${escapeHtml(state.livePerformanceDateFilter)} 매매 기록이 없습니다.` : "아직 실전 매매 성과 기록이 없습니다."}</article>`;
  if (dailyNode) {
    const dailyRows = Array.isArray(performance.daily_realized) ? performance.daily_realized : [];
    dailyNode.innerHTML = dailyRows.length
      ? dailyRows.slice(0, 8).map((row) => {
        const pnl = Number(row.pnl || 0);
        return `
          <article>
            <span>${escapeHtml(row.date || "-")}</span>
            <b class="${pnl >= 0 ? "up" : "down"}">${formatSignedKrw(pnl)}</b>
            <small>${Number(row.count || 0)}건 · 승 ${Number(row.wins || 0)} / 패 ${Number(row.losses || 0)}</small>
          </article>
        `;
      }).join("")
      : `<article><span>일자별 정산 없음</span><b>-</b><small>매도 정산 후 표시됩니다.</small></article>`;
  }
  if (reviewNode) {
    const review = performance.latest_review?.review || null;
    if (review) {
      const rule = Array.isArray(review.next_rules) && review.next_rules.length ? review.next_rules[0] : "다음 매매 때 진입·청산 근거를 더 촘촘히 기록합니다.";
      const good = Array.isArray(review.good_points) && review.good_points.length ? review.good_points[0] : "복기 가능한 실전 매매 데이터가 저장됐습니다.";
      const improve = Array.isArray(review.improvements) && review.improvements.length ? review.improvements[0] : "비교 후보와 후속 후보 기록을 보강합니다.";
      reviewNode.innerHTML = `
        <article class="live-trade-review-card">
          <span>${escapeHtml(review.name || review.symbol || "종목")} · ${pct(review.pnl_pct)}</span>
          <b class="${Number(review.pnl || 0) >= 0 ? "up" : "down"}">${formatSignedKrw(review.pnl)}</b>
          <small>${escapeHtml(review.summary || "최신 실전 매매 복기 저장 완료")}</small>
          <p><strong>잘한 점</strong>${escapeHtml(good)}</p>
          <p><strong>보완점</strong>${escapeHtml(improve)}</p>
          <p><strong>다음 규칙</strong>${escapeHtml(rule)}</p>
        </article>
      `;
    } else {
      reviewNode.innerHTML = `<article><span>복기 대기</span><b>-</b><small>실전 청산 매매가 생기면 자동으로 작성됩니다.</small></article>`;
    }
  }
}

async function loadLivePerformance() {
  const rowsNode = el("#livePerformanceRows");
  if (!rowsNode) return;
  try {
    const response = await fetch("/api/ops/live-performance");
    const result = await response.json();
    renderLivePerformance(result);
  } catch (error) {
    state.livePerformance = { ok: false, realized: [], open_lots: [], message: error.message };
    setText("livePerformanceState", "조회 실패");
    rowsNode.innerHTML = `<article class="live-performance-empty">실전 매매 성과 조회 실패: ${escapeHtml(error.message || "-")}</article>`;
  }
}

function renderBrokerExecutionJournal(report = state.latestBrokerJournal) {
  const node = el("#brokerExecutionJournalRows");
  if (!node) return;
  if (!report) {
    node.innerHTML = `<article class="live-performance-empty">최근 한투 체결 매매일지를 확인하는 중입니다.</article>`;
    return;
  }
  state.latestBrokerJournal = report;
  if (!report.ok) {
    node.innerHTML = `
      <article class="live-broker-journal-card empty">
        <div>
          <strong>저장된 체결 매매일지 없음</strong>
          <span>${escapeHtml(report.message || "체결 조회 후 매매일지가 자동으로 쌓입니다.")}</span>
        </div>
        <small>${escapeHtml(report.safety || "조회 전용입니다. 실제 주문은 실행하지 않습니다.")}</small>
      </article>
    `;
    return;
  }
  const realized = report.realized_preview || {};
  const pnl = Number(realized.total_pnl || 0);
  const previewLines = Array.isArray(report.preview_lines) ? report.preview_lines : [];
  node.innerHTML = `
    <article class="live-broker-journal-card ${pnl >= 0 ? "profit" : "loss"}">
      <div class="live-broker-journal-top">
        <div>
          <strong>${formatSignedKrw(pnl)} <small>${pct(realized.total_pnl_pct)}</small></strong>
          <span>${escapeHtml(report.date || "-")} · 체결 ${Number(report.count || 0).toLocaleString()}건 · 짝지은 매매 ${Number(realized.realized_count || 0).toLocaleString()}건</span>
        </div>
        <b>${escapeHtml(formatDateTimeShort(report.created_at || ""))}</b>
      </div>
      <div class="live-broker-journal-preview">
        ${previewLines.slice(0, 6).map((line) => `<span>${escapeHtml(line.replace(/^#+\s*/, ""))}</span>`).join("")}
      </div>
      <small>노트: ${escapeHtml(report.path || "-")}</small>
      <em>${escapeHtml(report.safety || "저장된 매매일지 읽기전용 조회입니다. 실제 주문은 실행하지 않습니다.")}</em>
    </article>
  `;
}

async function loadBrokerExecutionJournal(silent = true) {
  const node = el("#brokerExecutionJournalRows");
  if (!node) return null;
  try {
    const response = await fetch("/api/kis/executions/journal/latest?limit=8");
    const result = await response.json();
    renderBrokerExecutionJournal(result);
    if (!silent) addLog("최근 한투 체결 매매일지를 갱신했습니다. 실제 주문은 실행하지 않았습니다.");
    return result;
  } catch (error) {
    renderBrokerExecutionJournal({ ok: false, message: `매매일지 조회 실패: ${error.message}`, safety: "조회 실패이며 실제 주문은 실행하지 않았습니다." });
    if (!silent) addLog(`최근 한투 체결 매매일지 조회 실패: ${error.message}`);
    return null;
  }
}

async function loadKisWatch() {
  const response = await fetch("/api/kis/watch?symbols=005930,000660,005380,035420,051910,006400");
  const result = await response.json();
  const node = el("#kisLiveQuotes");
  if (!node) return;
  const items = result.items || [];
  node.innerHTML = items.length
    ? items.map((item) => {
      const ok = Boolean(item.ok);
      const change = Number(item.change_pct || 0);
      const meta = symbolMeta(item.symbol, item);
      return `<div class="live-card ${ok ? "" : "failed"}">
        <strong>${escapeHtml(meta.name)}</strong>
        <span class="${quoteClass(change)}">${ok ? `${Number(item.price || 0).toLocaleString()}원` : t.dataFail}</span>
        <small>${escapeHtml(symbolSubLabel(meta))} · ${ok ? pct(change) : item.message || "-"} · ${item.source || t.sourceKis}</small>
      </div>`;
    }).join("")
    : `<div class="event">${t.waiting}</div>`;
}

async function loadKisAccount() {
  const node = el("#kisAccountSnapshot");
  if (!node) return;
  try {
    const response = await fetch("/api/kis/account");
    const result = await response.json();
    state.liveAccountSnapshot = result;
    renderAccountDashboard();
    const summary = result.summary || {};
    if (!result.ok) {
      node.innerHTML = `<div class="macro-card failed"><strong>계좌 조회 실패</strong><span>${escapeHtml(result.message || t.dataFail)}</span><small>${escapeHtml(result.account_masked || "-")} · ${escapeHtml(result.mode || "-")}</small></div>`;
      return;
    }
    const positions = Array.isArray(result.positions) ? result.positions : [];
    node.innerHTML = `
      <div class="macro-card">
        <strong>주문가능 현금</strong>
        <span>${Number(summary.available_cash || summary.cash || 0).toLocaleString()}원</span>
        <small>예수금 ${Number(summary.deposit_cash || summary.settlement_cash || summary.cash || 0).toLocaleString()}원 · ${escapeHtml(result.account_masked || "-")}</small>
      </div>
      <div class="macro-card">
        <strong>실제 운용잔고</strong>
        <span>${Number(summary.net_liquidation_value || summary.total_value || 0).toLocaleString()}원</span>
        <small>주식평가 ${Number(summary.stock_value || 0).toLocaleString()}원 · 원장총액 ${Number(summary.broker_total_value || 0).toLocaleString()}원</small>
      </div>
      <div class="macro-card ${positions.length ? "" : "summary"}">
        <strong>보유 종목</strong>
        <span>${positions.length}개</span>
        <small>${positions.slice(0, 3).map((item) => `${escapeHtml(rowDisplayName(item))} ${Number(item.quantity || 0).toLocaleString()}주`).join(" · ") || "보유 종목 없음"}</small>
      </div>
    `;
  } catch (error) {
    state.liveAccountSnapshot = { ok: false, summary: {}, positions: [], message: error.message, safety: "실계좌 조회 실패" };
    renderAccountDashboard();
    node.innerHTML = `<div class="macro-card failed"><strong>한투 실제 계좌</strong><span>${t.dataFail}</span><small>${escapeHtml(error.message || "-")}</small></div>`;
  }
}

async function loadDartDisclosures() {
  const node = el("#dartDisclosureList");
  if (!node) return;
  try {
    const response = await fetch("/api/dart/disclosures?corp_code=00126380&days=7&page_count=6");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || result.message || `HTTP ${response.status}`);
    if (!result.configured) {
      node.innerHTML = `<div class="event">${escapeHtml(result.message || t.apiMissing)}</div>`;
      return;
    }
    const items = result.items || [];
    node.innerHTML = items.length
      ? items.map((item) => `<div class="event"><strong>${escapeHtml(item.rcept_dt || "-")}</strong> ${escapeHtml(item.corp_name || "")} ${escapeHtml(item.report_nm || "")}</div>`).join("")
      : `<div class="event">${escapeHtml(result.message || t.dartEmpty)}</div>`;
  } catch (error) {
    node.innerHTML = `<div class="event failed"><strong>DART 조회 실패</strong> ${escapeHtml(error.message || t.dataFail)}</div>`;
  }
}

function macroValue(row) {
  if (row.value === null || row.value === undefined || Number.isNaN(Number(row.value))) return "-";
  const value = Number(row.value);
  const unit = row.unit || "";
  if (unit === "%") return `${value.toFixed(2)}%`;
  if (unit === "원") return `${value.toLocaleString()}원`;
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit ? ` ${escapeHtml(unit)}` : ""}`;
}

function renderMacroCard(title, snapshot) {
  const rows = Array.isArray(snapshot.rows) ? snapshot.rows : [];
  const visibleRows = rows.slice(0, 5);
  const body = visibleRows.length
    ? visibleRows.map((row) => `
      <li>
        <span>${escapeHtml(row.name || row.id || row.series_id || row.stat_code || "-")}</span>
        <strong>${macroValue(row)}</strong>
        <small>${escapeHtml(row.time || "-")}</small>
      </li>
    `).join("")
    : `<li><span>${escapeHtml(snapshot.message || t.macroMissing)}</span><strong>-</strong><small>-</small></li>`;
  return `
    <div class="macro-card ${snapshot.ok ? "" : "failed"}">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(snapshot.stance || t.waiting)}</span>
      <small>${escapeHtml(snapshot.source || "-")} · ${snapshot.configured ? t.apiReady : t.apiMissing}</small>
      <ul>${body}</ul>
    </div>
  `;
}

async function loadMacroSnapshot(canFetch = true) {
  const node = el("#macroSnapshotList");
  if (!node) return;
  if (!canFetch) {
    state.macroSnapshot = null;
    node.innerHTML = `<div class="macro-card failed"><strong>${t.macroLiveTitle}</strong><span>${t.apiMissing}</span><small>${t.macroMissing}</small></div>`;
    return;
  }
  try {
    const response = await fetch("/api/macro/snapshot");
    const result = await response.json();
    state.macroSnapshot = result;
    node.innerHTML = `
      ${renderMacroCard("국내 거시 · ECOS", result.ecos || {})}
      ${renderMacroCard("미국 거시 · FRED", result.fred || {})}
      <div class="macro-card summary">
        <strong>AI 거시 요약</strong>
        <span>${escapeHtml(result.summary || t.waiting)}</span>
        <small>${escapeHtml(result.generated_at || "-")}</small>
      </div>
    `;
  } catch (error) {
    node.innerHTML = `<div class="macro-card failed"><strong>${t.macroLiveTitle}</strong><span>${t.dataFail}</span><small>${escapeHtml(error.message || "-")}</small></div>`;
  }
}

async function runBacktest() {
  const params = new URLSearchParams({
    symbol: el("#symbol").value.toUpperCase(),
    start: el("#startDate").value,
    end: el("#endDate").value,
    fast: el("#fast").value,
    slow: el("#slow").value,
  });
  const response = await fetch(`/api/backtest/range?${params.toString()}`);
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "\ubc31\ud14c\uc2a4\ud2b8 \uc2e4\ud328");
  const previousActive = state.active;
  state.active = result.symbol;
  if (previousActive !== state.active) {
    state.priceChart.symbol = "";
    tickMarket(true).catch((error) => addLog(`전략 종목 시장 데이터 갱신 실패: ${error.message}`));
  }
  state.equity = result.equity_curve;
  setText("finalEquity", `$${money(result.final_equity)}`);
  setText("totalReturn", pct(result.total_return_pct));
  setText("maxDrawdown", `${Number(result.max_drawdown_pct).toFixed(2)}%`);
  setText("tradeCount", result.trade_count);
  renderTradeQuality(result.trade_quality || {});
  renderBacktestRiskGate(result.risk_gate || {});
  el("#trades").innerHTML = result.trades.length
    ? result.trades.map((trade) => `<div class="trade"><span class="${trade.side === "BUY" ? "up" : "down"}">${trade.side === "BUY" ? t.buy : t.sell}</span><span>${trade.day}\uc77c</span><span>$${money(trade.price)}</span></div>`).join("")
    : `<div class="trade"><span class="flat">${t.waiting}</span><span>-</span><span>${t.waitSignal}</span></div>`;
  setText("dashReturn", pct(result.total_return_pct));
  const preset = selectedPreset();
  const resultName = symbolDisplayName(result.symbol, result);
  setText("strategyChartNote", `${preset.name} · ${preset.owner} · ${resultName} ${result.start_date}~${result.end_date} · ${dataSourceLabel(result)} · 전략 ${pct(result.total_return_pct)} / 보유 ${pct(result.buy_hold_return_pct)}`);
  drawCompareChart([result]);
  addLog(`${t.runBacktest} ${resultName}: ${result.total_return_pct}%`);
  renderMarket();
  loadLivePilotPlan(true);
}

async function runMultiBacktest() {
  const params = new URLSearchParams({
    symbols: state.selectedResearchSymbols.join(","),
    start: el("#startDate").value,
    end: el("#endDate").value,
    fast: el("#fast").value,
    slow: el("#slow").value,
  });
  const response = await fetch(`/api/backtest/multi?${params.toString()}`);
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "\ub2e4\uc911\ube44\uad50 \uc2e4\ud328");
  state.lastMultiBacktest = result;
  drawCompareChart(result.results || []);
  const best = result.best || {};
  const preset = selectedPreset();
  const bestName = best.symbol ? symbolDisplayName(best.symbol, best) : "-";
  setText("strategyChartNote", `${preset.name} · ${preset.owner} · ${result.start_date}~${result.end_date} · ${dataSourceLabel(result)} · 최고 ${bestName} ${pct(Number(best.total_return_pct || 0))}`);
  el("#multiCompareList").innerHTML = (result.ranked || []).map((row, index) => `
    <div class="candidate">
      <strong>${index + 1}. ${escapeHtml(symbolDisplayName(row.symbol, row))} <span class="${Number(row.total_return_pct) >= 0 ? "up" : "down"}">${pct(row.total_return_pct)}</span></strong>
      <small>\uc804\ub7b5 \ucd5c\uc885 $${money(row.final_equity)} · \ubcf4\uc720 ${pct(row.buy_hold_return_pct)} · MDD ${row.max_drawdown_pct}%</small>
      <small>\uc0e4\ud504 ${row.sharpe} · \ub9e4\ub9e4 ${row.trade_count}\ud68c · 승률 ${Number(row.trade_quality?.win_rate_pct || 0).toFixed(1)}% · PF ${Number(row.trade_quality?.profit_factor || 0).toFixed(2)} · ${escapeHtml(dataSourceLabel(row))}</small>
    </div>
  `).join("");
  if (result.results && result.results[0]) {
    const first = result.results[0];
    setText("finalEquity", `$${money(first.final_equity)}`);
    setText("totalReturn", pct(first.total_return_pct));
    setText("maxDrawdown", `${Number(first.max_drawdown_pct).toFixed(2)}%`);
    setText("tradeCount", first.trade_count);
    renderTradeQuality(first.trade_quality || {});
    renderBacktestRiskGate(first.risk_gate || {});
  }
  addLog(`${t.runMultiBacktest}: ${state.selectedResearchSymbols.map((symbol) => symbolDisplayName(symbol)).join(", ")}`);
}

function drawHistoricalReplayChart(result) {
  const canvas = el("#historicalReplayChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const values = Array.isArray(result.equity_curve) ? result.equity_curve.map(Number).filter(Number.isFinite) : [];
  const dates = Array.isArray(result.dates) ? result.dates : [];
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#071014";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(119, 225, 184, .12)";
  ctx.lineWidth = 1;
  const left = 58;
  const right = 26;
  const top = 20;
  const bottom = 42;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  for (let i = 0; i <= 4; i += 1) {
    const y = top + (chartHeight / 4) * i;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(width - right, y);
    ctx.stroke();
  }
  if (values.length < 2) {
    ctx.fillStyle = "rgba(237,244,248,.75)";
    ctx.fillText("과거장 훈련을 실행하면 자산 곡선이 표시됩니다.", left, height / 2);
    return;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(1, max - min);
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = left + (chartWidth * index) / Math.max(1, values.length - 1);
    const y = top + chartHeight - ((value - min) / range) * chartHeight;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = "#77e1b8";
  ctx.lineWidth = 3;
  ctx.stroke();
  ctx.fillStyle = "rgba(237,244,248,.72)";
  ctx.font = "12px Consolas, Malgun Gothic, sans-serif";
  ctx.textAlign = "right";
  for (let i = 0; i <= 4; i += 1) {
    const value = max - (range / 4) * i;
    const y = top + (chartHeight / 4) * i + 4;
    ctx.fillText(money(value), left - 8, y);
  }
  ctx.textAlign = "center";
  const labelCount = Math.min(6, dates.length);
  for (let i = 0; i < labelCount; i += 1) {
    const index = Math.round((dates.length - 1) * (i / Math.max(1, labelCount - 1)));
    const x = left + (chartWidth * index) / Math.max(1, dates.length - 1);
    ctx.fillText(String(dates[index] || "").slice(0, 7), x, height - 16);
  }
}

function renderHistoricalReplay(result) {
  const strategyLabel = result.strategy_label || "과거장 훈련";
  setText("replayState", `${strategyLabel} · ${result.start_date || "-"}~${result.end_date || "-"} · ${result.symbols?.length || 0}종목 · ${dataSourceLabel(result)}`);
  setText("replayReturn", pct(result.total_return_pct || 0));
  setText("replayMdd", `${Number(result.max_drawdown_pct || 0).toFixed(2)}%`);
  setText("replayTrades", `${result.trade_count || 0}회`);
  setText("replayWinRate", `${Number(result.win_rate_pct || 0).toFixed(1)}%`);
  setText("replayHours", `${Number(result.compressed_training_hours || 0).toLocaleString()}시간`);
  const latest = result.latest_period_returns || {};
  setText("replayDailyReturn", latest.daily ? pct(latest.daily.return_pct || 0) : "-");
  setText("replayWeeklyReturn", latest.weekly ? pct(latest.weekly.return_pct || 0) : "-");
  setText("replayMonthlyReturn", latest.monthly ? pct(latest.monthly.return_pct || 0) : "-");
  const trades = Array.isArray(result.trades) ? result.trades.slice(-14).reverse() : [];
  const tradeNode = el("#replayTradeRows");
  if (tradeNode) {
    tradeNode.innerHTML = trades.length
      ? trades.map((trade) => `
        <div class="replay-row ${trade.side === "BUY" ? "buy" : "sell"}">
          <b>${escapeHtml(trade.date || "-")} ${escapeHtml(trade.side || "-")}</b>
          <span>${escapeHtml(symbolDisplayName(trade.symbol, trade))} · ${money(trade.price || 0)} · ${money(trade.notional || 0)}</span>
          <small>${escapeHtml(trade.reason || "-")}${trade.pnl_pct !== undefined ? ` · 손익 ${pct(trade.pnl_pct)}` : ""}</small>
        </div>
      `).join("")
      : `<div class="replay-row"><b>매매 없음</b><span>해당 기간에는 전략 조건이 발생하지 않았습니다.</span></div>`;
  }
  const logs = Array.isArray(result.experience_log) ? result.experience_log.slice(-14).reverse() : [];
  const logNode = el("#replayExperienceRows");
  if (logNode) {
    logNode.innerHTML = logs.length
      ? logs.map((row) => `
        <div class="replay-row">
          <b>${escapeHtml(row.date || "-")} · 평가 ${money(row.equity || 0)}</b>
          <span>포지션 ${row.positions || 0}개 · DD ${Number(row.drawdown_pct || 0).toFixed(2)}%</span>
          <small>${escapeHtml(row.lesson || "-")}</small>
        </div>
      `).join("")
      : `<div class="replay-row"><b>경험 로그 대기</b><span>훈련 실행 후 날짜별 복기 로그가 표시됩니다.</span></div>`;
  }
  const meeting = Array.isArray(result.staff_meeting) ? result.staff_meeting : [];
  const meetingNode = el("#replayStaffMeetingRows");
  if (meetingNode) {
    meetingNode.innerHTML = meeting.length
      ? meeting.map((row) => `
        <div class="replay-row staff">
          <b>${escapeHtml(row.speaker || "-")} · ${escapeHtml(row.stance || "-")}</b>
          <span>${escapeHtml(row.message || "-")}</span>
        </div>
      `).join("")
      : `<div class="replay-row"><b>회의 대기</b><span>훈련 실행 후 운용 AI와 연구 AI의 회의 로그가 표시됩니다.</span></div>`;
  }
  drawHistoricalReplayChart(result);
}

async function loadReplayHistory() {
  const node = el("#replayHistoryRows");
  if (!node) return;
  try {
    const response = await fetch("/api/paper/replay/history?limit=10");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "기록 조회 실패");
    const rows = Array.isArray(result.runs) ? result.runs : [];
    node.innerHTML = rows.length
      ? rows.map((row) => `
        <div class="replay-row">
          <b>${escapeHtml(row.strategy_label || row.strategy_mode || "훈련")} · ${escapeHtml((row.generated_at || "").slice(0, 16))}</b>
          <span>${escapeHtml((row.symbols || []).slice(0, 5).map((symbol) => symbolDisplayName(symbol)).join(", "))} · ${escapeHtml(row.start_date || "-")}~${escapeHtml(row.end_date || "-")}</span>
          <small>수익 ${pct(row.total_return_pct || 0)} · MDD ${Number(row.max_drawdown_pct || 0).toFixed(2)}% · 매매 ${row.trade_count || 0}회</small>
        </div>
      `).join("")
      : `<div class="replay-row"><b>훈련 기록 없음</b><span>과거장 훈련을 실행하면 여기에 계속 쌓입니다.</span></div>`;
  } catch (error) {
    node.innerHTML = `<div class="replay-row"><b>기록 조회 실패</b><span>${escapeHtml(error.message)}</span></div>`;
  }
}

async function runHistoricalReplay() {
  const symbols = (state.replaySelectedSymbols.join(",") || el("#replaySymbols")?.value || state.selectedResearchSymbols.join(",") || el("#symbol")?.value || "083450,005930,NVDA").trim();
  if (el("#replaySymbols")) el("#replaySymbols").value = symbols;
  const params = new URLSearchParams({
    symbols,
    start: el("#startDate").value,
    end: el("#endDate").value,
    strategy: el("#replayStrategy")?.value || "ma_cross",
    fast: el("#fast").value,
    slow: el("#slow").value,
    cash: el("#replayCash")?.value || "100000000",
    allocation: el("#replayAllocation")?.value || "25",
    max_positions: el("#replayMaxPositions")?.value || "4",
    stop_loss: el("#replayStopLoss")?.value || "8",
    take_profit: el("#replayTakeProfit")?.value || "0",
    holding_limit: el("#replayHoldingLimit")?.value || "0",
    cycles_per_day: el("#replayCyclesPerDay")?.value || "24",
  });
  try {
    setText("replayState", "과거장 훈련 실행 중");
    const response = await fetch(`/api/paper/replay?${params.toString()}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "과거장 훈련 실패");
    state.lastHistoricalReplay = result;
    renderHistoricalReplay(result);
    loadReplayHistory();
    addLog(`과거장 모의훈련 완료: ${result.summary || ""}`);
  } catch (error) {
    setText("replayState", "훈련 실패");
    addLog(`과거장 모의훈련 실패: ${error.message}`);
  }
}

function renderDailyReplayDrill(result = {}) {
  const best = result.best || {};
  const worst = result.worst || {};
  const runs = Array.isArray(result.runs) ? result.runs : [];
  setText("replayState", `장마감 10회 복기 · ${result.target_date || "-"} · ${result.completed_repeats || 0}/${result.repeats_requested || 0}회 · 실주문 없음`);
  setText("replayReturn", pct(result.average_return_pct || 0));
  setText("replayMdd", `${Number(worst.max_drawdown_pct || 0).toFixed(2)}%`);
  setText("replayTrades", `${result.total_trade_count || 0}회`);
  setText("replayWinRate", best.win_rate_pct !== undefined ? `${Number(best.win_rate_pct || 0).toFixed(1)}%` : "-");
  setText("replayHours", `${Number((result.completed_repeats || 0) * 10).toLocaleString()}회차`);
  setText("replayDailyReturn", best.return_pct !== undefined ? pct(best.return_pct || 0) : "-");
  setText("replayWeeklyReturn", worst.return_pct !== undefined ? pct(worst.return_pct || 0) : "-");
  setText("replayMonthlyReturn", `${Number(result.failed_repeats || 0)}실패`);
  const tradeNode = el("#replayTradeRows");
  if (tradeNode) {
    tradeNode.innerHTML = runs.length
      ? runs.slice(0, 10).map((row) => `
        <div class="replay-row ${Number(row.return_pct || 0) >= 0 ? "buy" : "sell"}">
          <b>${Number(row.iteration || 0)}회차 · ${escapeHtml(row.label || row.strategy_label || "-")}</b>
          <span>${escapeHtml((row.symbols || []).map((symbol) => symbolDisplayName(symbol)).join(", "))}</span>
          <small>수익 ${pct(row.return_pct || 0)} · MDD ${Number(row.max_drawdown_pct || 0).toFixed(2)}% · 매매 ${row.trade_count || 0}회</small>
        </div>
      `).join("")
      : `<div class="replay-row"><b>훈련 실패</b><span>${escapeHtml(result.errors?.[0]?.error || "실행 가능한 반복 결과가 없습니다.")}</span></div>`;
  }
  const logNode = el("#replayExperienceRows");
  if (logNode) {
    logNode.innerHTML = `
      <div class="replay-row">
        <b>오늘 복기 결론</b>
        <span>${escapeHtml(result.lesson || "장마감 복기훈련 결과를 기다리는 중입니다.")}</span>
        <small>${escapeHtml(result.safety || "실제 주문은 실행하지 않습니다.")}</small>
      </div>
      <div class="replay-row">
        <b>최고 반복</b>
        <span>${escapeHtml(best.label || "-")} · 수익 ${pct(best.return_pct || 0)} · 매매 ${best.trade_count || 0}회</span>
      </div>
      <div class="replay-row">
        <b>최저 반복</b>
        <span>${escapeHtml(worst.label || "-")} · 수익 ${pct(worst.return_pct || 0)} · 매매 ${worst.trade_count || 0}회</span>
      </div>
    `;
  }
  const meetingNode = el("#replayStaffMeetingRows");
  if (meetingNode) {
    const errors = Array.isArray(result.errors) ? result.errors : [];
    meetingNode.innerHTML = `
      <div class="replay-row staff">
        <b>연구 AI · 복기</b>
        <span>당일 거래대금/상승률 후보를 10가지 조건으로 반복 훈련했습니다.</span>
      </div>
      <div class="replay-row staff">
        <b>매매 AI · 다음 행동</b>
        <span>최고 반복의 진입/청산 조건을 다음 장 후보 필터와 승인 전 점검에 반영합니다.</span>
      </div>
      ${errors.length ? `<div class="replay-row staff"><b>데이터 실패</b><span>${errors.length}회 실패. 데이터가 부족한 종목/구간은 다음 드릴에서 제외합니다.</span></div>` : ""}
    `;
  }
  drawHistoricalReplayChart({ equity_curve: [], dates: [] });
}

async function runDailyReplayDrill() {
  const symbols = (state.replaySelectedSymbols.join(",") || el("#replaySymbols")?.value || state.selectedResearchSymbols.join(",") || "").trim();
  const params = new URLSearchParams({
    symbols,
    repeats: el("#dailyReplayRepeats")?.value || "10",
    cash: el("#replayCash")?.value || "150000",
    lookback_days: "160",
    source: "manual-ui-daily-replay-drill",
  });
  try {
    setText("replayState", "장마감 10회 복기훈련 실행 중");
    const response = await fetch(`/api/paper/daily-replay-drill?${params.toString()}`);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.error || "장마감 복기훈련 실패");
    state.lastDailyReplayDrill = result;
    renderDailyReplayDrill(result);
    loadReplayHistory();
    addLog(`장마감 10회 복기훈련 완료: ${result.lesson || ""}`);
  } catch (error) {
    setText("replayState", "장마감 복기훈련 실패");
    addLog(`장마감 10회 복기훈련 실패: ${error.message}`);
  }
}

function parseNumberGrid(value, fallback) {
  const parsed = String(value || "")
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item) && item > 0);
  return parsed.length ? parsed : fallback;
}

function applyValidationScenario() {
  const scenario = el("#validationScenario")?.value || "balanced";
  const presets = {
    fast: { fast: "3,5,8,12,16", slow: "20,32,50,80" },
    balanced: { fast: "5,8,12,20,30", slow: "24,32,50,80,120" },
    conservative: { fast: "10,12,20,30,45", slow: "50,80,120,160,200" },
  };
  const preset = presets[scenario] || presets.balanced;
  if (el("#fastGrid")) el("#fastGrid").value = preset.fast;
  if (el("#slowGrid")) el("#slowGrid").value = preset.slow;
}

function scoreClass(score) {
  const value = Number(score || 0);
  if (value >= 55) return "hot";
  if (value >= 25) return "warm";
  if (value >= 0) return "cool";
  return "cold";
}

function gateCheckLabel(name) {
  return {
    min_trade_count: "거래 횟수",
    min_win_rate_pct: "승률",
    min_expectancy_pct: "기대값",
    min_profit_factor: "손익비",
    max_drawdown_pct: "최대낙폭",
    max_consecutive_losses: "연속손실",
  }[name] || name;
}

function renderValidationSuite(result) {
  const best = result.best || {};
  const decision = result.decision || {};
  const gate = best.risk_gate || {};
  const gateSummary = gate.summary || {};
  const failedChecks = Array.isArray(gate.failed) ? gate.failed : [];
  const reasons = Array.isArray(decision.reasons) ? decision.reasons : [];
  const nextActions = Array.isArray(decision.next_actions) ? decision.next_actions : [];
  const warnings = result.warnings || [];
  const ranked = result.ranked || [];
  const matrix = result.matrix || [];
  const walkForward = result.walk_forward || {};
  const wfSummary = walkForward.summary || {};
  const wfSegments = Array.isArray(walkForward.segments) ? walkForward.segments : [];
  const wfScore = Number(wfSummary.stability_score || 0);
  const wfClass = wfScore >= 70 ? "pass" : wfScore >= 45 ? "review" : "hold";
  const stressTest = result.stress_test || {};
  const stressSummary = stressTest.summary || {};
  const stressSamples = Array.isArray(stressTest.sample_returns_pct) ? stressTest.sample_returns_pct : [];
  const stressScore = Number(stressSummary.resilience_score || 0);
  const stressClass = stressScore >= 70 ? "pass" : stressScore >= 45 ? "review" : "hold";
  const stressMin = stressSamples.length ? Math.min(...stressSamples) : 0;
  const stressMax = stressSamples.length ? Math.max(...stressSamples) : 0;
  const stressRange = Math.max(1, stressMax - stressMin);
  const stressBars = stressSamples.map((value) => {
    const numeric = Number(value || 0);
    const height = Math.max(8, Math.min(100, 8 + ((numeric - stressMin) / stressRange) * 92));
    return `<span class="${numeric >= 0 ? "gain" : "loss"}" style="height:${height}%"><i>${pct(numeric)}</i></span>`;
  }).join("");
  const parameter = result.parameter_robustness || {};
  const paramSummary = parameter.summary || {};
  const paramNeighbors = Array.isArray(parameter.neighbors) ? parameter.neighbors : [];
  const paramScore = Number(paramSummary.plateau_score || 0);
  const paramClass = paramScore >= 70 ? "pass" : paramScore >= 45 ? "review" : "hold";
  const relative = result.relative_performance || {};
  const relativeSummary = relative.summary || {};
  const relativeScore = Number(relativeSummary.relative_score || 0);
  const relativeClass = relativeScore >= 70 ? "pass" : relativeScore >= 45 ? "review" : "hold";
  const relativeRows = [
    { label: "전략", value: Number(relative.strategy?.return_pct || 0), mdd: Number(relative.strategy?.max_drawdown_pct || 0), key: "strategy" },
    { label: "종목 보유", value: Number(relative.buy_hold?.return_pct || 0), mdd: Number(relative.buy_hold?.max_drawdown_pct || 0), key: "hold" },
    { label: `${relative.benchmark || "SPY"} 보유`, value: Number(relative.benchmark_hold?.return_pct || 0), mdd: Number(relative.benchmark_hold?.max_drawdown_pct || 0), key: "benchmark" },
  ];
  const relativeAbsMax = Math.max(1, ...relativeRows.map((row) => Math.abs(row.value)));
  const promotion = result.promotion_review || {};
  const promotionScore = Number(promotion.readiness_score || 0);
  const promotionStage = String(promotion.stage || "WAIT").toLowerCase();
  const promotionClass = promotionStage === "paper_ready" ? "pass" : promotionStage === "blocked" ? "hold" : promotionStage === "review" ? "review" : "wait";
  const promotionChecks = Array.isArray(promotion.checks) ? promotion.checks : [];
  const promotionBlockers = Array.isArray(promotion.blockers) ? promotion.blockers : [];
  const promotionReviewItems = Array.isArray(promotion.review_items) ? promotion.review_items : [];
  const promotionActions = Array.isArray(promotion.next_actions) ? promotion.next_actions : [];
  const rawDecisionStatus = String(decision.status || gate.status || "WAIT").toUpperCase();
  const decisionClass = rawDecisionStatus === "PASSED" ? "pass" : rawDecisionStatus === "BLOCKED" ? "hold" : rawDecisionStatus.toLowerCase();
  const gateStatus = String(decision.risk_gate_status || gate.status || "WAIT").toUpperCase();
  const gateLabel = { PASSED: "통과", REVIEW: "검토", BLOCKED: "차단", WAIT: "대기" }[gateStatus] || gateStatus;
  const reasonItems = (reasons.length ? reasons : ["검증 결과를 기다리는 중입니다."]).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const actionItems = (nextActions.length ? nextActions : ["검증 실행 후 보호장치와 강건성 결과를 함께 확인하세요."]).map((item) => `<li>${escapeHtml(replaceSymbolCodesInText(item))}</li>`).join("");
  const failedItems = failedChecks.slice(0, 4).map((item) => {
    const value = item.value ?? "-";
    const required = item.required ?? "-";
    return `<span>${escapeHtml(gateCheckLabel(item.name))} ${escapeHtml(value)}/${escapeHtml(required)}</span>`;
  }).join("");
  const validationName = symbolDisplayName(result.symbol, result);
  setText("validationSummary", `${validationName} · ${result.start_date}~${result.end_date} · ${ranked.length}개 후보 평가`);
  el("#validationDecision").innerHTML = `
    <div class="decision-card ${decisionClass}">
      <div class="decision-main">
        <small>AI 검증 판정</small>
        <strong>${escapeHtml(decision.label || "검증 대기")}</strong>
        <p>${escapeHtml(decision.summary || "최적화 결과를 기다리는 중입니다.")}</p>
      </div>
      <div class="decision-metrics">
        <div><small>보호장치</small><strong>${escapeHtml(gateLabel)}</strong><span>${escapeHtml(decision.risk_gate_message || gate.message || "대기")}</span></div>
        <div><small>검증수익</small><strong class="${Number(best.test_return_pct || 0) >= 0 ? "up" : "down"}">${pct(best.test_return_pct || 0)}</strong><span>점수 ${Number(best.score || 0).toFixed(1)}</span></div>
        <div><small>낙폭/PF</small><strong>${pct(best.test_drawdown_pct || 0)} / ${Number(best.profit_factor || 0).toFixed(2)}</strong><span>승률 ${Number(best.win_rate_pct || gateSummary.win_rate_pct || 0).toFixed(1)}%</span></div>
        <div><small>거래/기대값</small><strong>${Number(best.trade_count || gateSummary.trade_count || 0)}</strong><span>${Number(gateSummary.expectancy_pct || 0).toFixed(2)}%</span></div>
      </div>
      <div class="decision-columns">
        <div><b>판단 근거</b><ul>${reasonItems}</ul></div>
        <div><b>다음 행동</b><ul>${actionItems}</ul></div>
      </div>
      ${failedItems ? `<div class="decision-failed"><b>보호장치 미통과</b>${failedItems}</div>` : ""}
    </div>
  `;
  el("#validationPromotion").innerHTML = promotion.label ? `
    <div class="promotion-card ${promotionClass}">
      <div class="promotion-head">
        <div><small>AI 운용 승급 심사</small><strong>${escapeHtml(promotion.label)}</strong><span>${escapeHtml(koreanStatusText(promotion.guardrail || "실거래 주문은 꺼짐 상태입니다."))}</span></div>
        <div><b>${promotionScore.toFixed(1)}</b><span>운용 준비도</span></div>
        <div><b>${escapeHtml(promotion.recommended_mode || "research_only")}</b><span>추천 모드</span></div>
        <div><b>${promotionBlockers.length}</b><span>차단 항목</span></div>
        <div><b>${promotionReviewItems.length}</b><span>검토 항목</span></div>
      </div>
      <div class="promotion-command">
        <button data-promote-validation ${promotion.stage === "PAPER_READY" ? "" : "disabled"}>모의투자 후보 큐 등록</button>
        <span>${promotion.stage === "PAPER_READY" ? "검증 조건을 서버에서 재확인한 뒤 후보 큐에 저장합니다." : "차단/검토 항목이 있으면 큐 등록을 막습니다."}</span>
      </div>
      <div class="promotion-grid">
        <div class="promotion-checks">
          ${promotionChecks.map((item) => `
            <span class="${item.ok ? "ok" : item.severity === "blocker" ? "fail" : "warn"}">
              <b>${item.ok ? "통과" : item.severity === "blocker" ? "차단" : "검토"}</b>
              ${escapeHtml(item.label)} <small>${escapeHtml(item.value)} / ${escapeHtml(item.required)}</small>
            </span>
          `).join("")}
        </div>
        <div class="promotion-actions">
          <b>다음 행동</b>
          <ul>${(promotionActions.length ? promotionActions : ["검증 결과를 확인한 뒤 후보 상태를 결정하세요."]).map((item) => `<li>${escapeHtml(replaceSymbolCodesInText(item))}</li>`).join("")}</ul>
        </div>
      </div>
    </div>
  ` : `<div class="validation-ok">운용 승급 심사 대기</div>`;
  el("#validationWarnings").innerHTML = warnings.length
    ? warnings.map((warning) => `<div class="validation-warning">${escapeHtml(warning)}</div>`).join("")
    : `<div class="validation-ok">과최적화/낙폭/거래횟수 기본 경고 없음. 그래도 실전 전 워크포워드와 보호장치를 같이 확인해야 합니다.</div>`;
  el("#validationBest").innerHTML = best.fast ? `
    <div class="best-card">
      <div><small>최고 후보</small><strong>MA ${best.fast}/${best.slow}</strong><span class="${Number(best.test_return_pct || 0) >= 0 ? "up" : "down"}">${pct(best.test_return_pct || 0)}</span></div>
      <div><small>검증 점수</small><strong>${Number(best.score || 0).toFixed(2)}</strong><span>${best.verdict || "-"}</span></div>
      <div><small>과최적화 차이</small><strong>${pct(best.overfit_gap_pct || 0)}</strong><span>학습 ${pct(best.train_return_pct || 0)}</span></div>
      <div><small>리스크</small><strong>MDD ${pct(best.test_drawdown_pct || 0)}</strong><span>PF ${Number(best.profit_factor || 0).toFixed(2)} · 승률 ${Number(best.win_rate_pct || 0).toFixed(1)}%</span></div>
      <button data-apply-optimized="${best.fast},${best.slow}">이 파라미터 적용</button>
    </div>
  ` : `<div class="validation-ok">아직 최고 후보가 없습니다.</div>`;
  el("#validationWalkForward").innerHTML = wfSegments.length ? `
    <div class="walk-card ${wfClass}">
      <div class="walk-head">
        <div><small>워크포워드 구간 검증</small><strong>${escapeHtml(wfSummary.verdict || "구간 검증")}</strong></div>
        <div><b>${wfScore.toFixed(1)}</b><span>안정성 점수</span></div>
        <div><b>${Number(wfSummary.pass_rate_pct || 0).toFixed(1)}%</b><span>통과 구간</span></div>
        <div><b>${pct(wfSummary.worst_return_pct || 0)}</b><span>최악 구간 수익</span></div>
        <div><b>${pct(wfSummary.worst_drawdown_pct || 0)}</b><span>최악 MDD</span></div>
      </div>
      <div class="walk-segments">
        ${wfSegments.map((segment) => {
          const segmentReturn = Number(segment.return_pct || 0);
          const barWidth = Math.min(100, Math.max(8, Math.abs(segmentReturn) * 2.2 + 12));
          return `
            <div class="wf-segment ${segment.passed ? "pass" : "fail"}">
              <div class="wf-label"><b>${segment.index}</b><span>${escapeHtml(segment.start_date)}~${escapeHtml(segment.end_date)}</span></div>
              <div class="wf-bar"><span class="${segmentReturn >= 0 ? "upbar" : "downbar"}" style="width:${barWidth}%"></span></div>
              <div class="wf-values"><strong class="${segmentReturn >= 0 ? "up" : "down"}">${pct(segmentReturn)}</strong><small>MDD ${pct(segment.max_drawdown_pct || 0)} · 거래 ${Number(segment.trade_count || 0)}</small></div>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  ` : `<div class="validation-ok">워크포워드 구간 검증 대기</div>`;
  el("#validationStress").innerHTML = stressSummary.verdict ? `
    <div class="stress-card ${stressClass}">
      <div class="stress-head">
        <div><small>몬테카를로 스트레스</small><strong>${escapeHtml(stressSummary.verdict)}</strong><span>${Number(stressTest.simulation_count || 0)}회 재표본</span></div>
        <div><b>${stressScore.toFixed(1)}</b><span>회복력 점수</span></div>
        <div><b>${Number(stressSummary.loss_probability_pct || 0).toFixed(1)}%</b><span>손실 확률</span></div>
        <div><b>${pct(stressSummary.p05_return_pct || 0)}</b><span>하위 5% 수익</span></div>
        <div><b>${pct(stressSummary.p05_drawdown_pct || 0)}</b><span>하위 5% MDD</span></div>
      </div>
      <div class="stress-body">
        <div class="stress-dist">${stressBars}</div>
        <div class="stress-notes">
          <span>중앙값 ${pct(stressSummary.median_return_pct || 0)}</span>
          <span>상위 5% ${pct(stressSummary.p95_return_pct || 0)}</span>
          <span>중앙 MDD ${pct(stressSummary.median_drawdown_pct || 0)}</span>
        </div>
      </div>
    </div>
  ` : `<div class="validation-ok">몬테카를로 스트레스 검증 대기</div>`;
  el("#validationParameter").innerHTML = paramSummary.verdict ? `
    <div class="parameter-card ${paramClass}">
      <div class="parameter-head">
        <div><small>파라미터 견고성</small><strong>${escapeHtml(paramSummary.verdict)}</strong><span>최고 MA ${parameter.fast}/${parameter.slow} 주변 조합</span></div>
        <div><b>${paramScore.toFixed(1)}</b><span>견고성 점수</span></div>
        <div><b>${Number(paramSummary.near_score_rate_pct || 0).toFixed(1)}%</b><span>근접 점수</span></div>
        <div><b>${pct(paramSummary.average_neighbor_return_pct || 0)}</b><span>주변 평균수익</span></div>
        <div><b>${pct(paramSummary.worst_neighbor_drawdown_pct || 0)}</b><span>주변 최악 MDD</span></div>
      </div>
      <div class="parameter-neighbors">
        ${paramNeighbors.map((row) => `
          <button class="param-chip ${row.is_best ? "best" : ""} ${row.near_score ? "near" : "weak"}" data-apply-optimized="${row.fast},${row.slow}">
            <b>MA ${row.fast}/${row.slow}</b>
            <span class="${Number(row.return_pct || 0) >= 0 ? "up" : "down"}">${pct(row.return_pct || 0)}</span>
            <small>점수 ${Number(row.score || 0).toFixed(1)} · MDD ${pct(row.max_drawdown_pct || 0)}</small>
          </button>
        `).join("")}
      </div>
    </div>
  ` : `<div class="validation-ok">파라미터 견고성 검증 대기</div>`;
  el("#validationRelative").innerHTML = relativeSummary.verdict ? `
    <div class="relative-card ${relativeClass}">
      <div class="relative-head">
        <div><small>상대성과 비교</small><strong>${escapeHtml(relativeSummary.verdict)}</strong><span>전략 vs 종목보유 vs ${escapeHtml(relative.benchmark || "SPY")}</span></div>
        <div><b>${relativeScore.toFixed(1)}</b><span>상대성과 점수</span></div>
        <div><b class="${Number(relativeSummary.excess_vs_hold_pct || 0) >= 0 ? "up" : "down"}">${pct(relativeSummary.excess_vs_hold_pct || 0)}</b><span>보유 대비</span></div>
        <div><b class="${Number(relativeSummary.excess_vs_benchmark_pct || 0) >= 0 ? "up" : "down"}">${pct(relativeSummary.excess_vs_benchmark_pct || 0)}</b><span>시장 대비</span></div>
        <div><b>${pct(relativeSummary.drawdown_edge_vs_hold_pct || 0)}</b><span>보유 대비 MDD 우위</span></div>
      </div>
      <div class="relative-bars">
        ${relativeRows.map((row) => {
          const width = Math.max(8, Math.min(100, Math.abs(row.value) / relativeAbsMax * 100));
          return `
            <div class="relative-row ${row.key}">
              <span>${escapeHtml(row.label)}</span>
              <div class="relative-track"><i class="${row.value >= 0 ? "gain" : "loss"}" style="width:${width}%"></i></div>
              <strong class="${row.value >= 0 ? "up" : "down"}">${pct(row.value)}</strong>
              <small>MDD ${pct(row.mdd)}</small>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  ` : `<div class="validation-ok">상대성과 비교 대기</div>`;
  el("#validationHeatmap").innerHTML = matrix.length
    ? matrix.map((row) => `
      <div class="heatmap-row">
        <b>F${row.fast}</b>
        ${(row.cells || []).map((cell) => cell.valid ? `
          <button class="heat-cell ${scoreClass(cell.score)}" data-apply-optimized="${cell.fast},${cell.slow}" title="MA ${cell.fast}/${cell.slow} · 수익 ${pct(cell.return_pct || 0)} · MDD ${pct(cell.mdd_pct || 0)}">
            <strong>S${cell.slow}</strong><span>${Number(cell.score || 0).toFixed(1)}</span>
          </button>
        ` : `<span class="heat-cell invalid">-</span>`).join("")}
      </div>
    `).join("")
    : `<div class="validation-ok">히트맵 대기</div>`;
  el("#validationRanked").innerHTML = ranked.slice(0, 10).map((row, index) => `
    <button class="rank-row" data-apply-optimized="${row.fast},${row.slow}">
      <b>${index + 1}</b>
      <strong>MA ${row.fast}/${row.slow}</strong>
      <span class="${Number(row.test_return_pct || 0) >= 0 ? "up" : "down"}">${pct(row.test_return_pct || 0)}</span>
      <small>점수 ${Number(row.score || 0).toFixed(1)} · MDD ${pct(row.test_drawdown_pct || 0)} · PF ${Number(row.profit_factor || 0).toFixed(2)} · ${escapeHtml(row.verdict)}</small>
    </button>
  `).join("");
  if (Array.isArray(result.top_results) && result.top_results.length) {
    drawCompareChart(result.top_results);
    const top = result.top_results[0];
    setText("strategyChartNote", `최적화 상위 후보 차트 · ${symbolDisplayName(top.symbol, top)} · MA ${top.fast_window}/${top.slow_window} · 점수 ${top.optimization_score}`);
  }
}

async function runValidationSuite() {
  const symbol = (el("#symbol").value || state.selectedResearchSymbols[0] || "AAPL").toUpperCase();
  const fastValues = parseNumberGrid(el("#fastGrid")?.value, [5, 8, 12, 20, 30]);
  const slowValues = parseNumberGrid(el("#slowGrid")?.value, [24, 32, 50, 80, 120]);
  state.lastValidationParams = {
    symbol,
    start_date: el("#startDate").value,
    end_date: el("#endDate").value,
    scenario: el("#validationScenario")?.value || "balanced",
    fast_values: fastValues,
    slow_values: slowValues,
  };
  const params = new URLSearchParams({
    symbol,
    start: state.lastValidationParams.start_date,
    end: state.lastValidationParams.end_date,
    scenario: state.lastValidationParams.scenario,
    fast_values: fastValues.join(","),
    slow_values: slowValues.join(","),
  });
  setText("validationSummary", `${symbolDisplayName(symbol)} 최적화 실행 중...`);
  const response = await fetch(`/api/backtest/optimize?${params.toString()}`);
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "전략 검증 실패");
  state.lastValidationResult = result;
  renderValidationSuite(result);
  addLog(`전략 검증 완료 ${symbolDisplayName(result.symbol, result)}: 최고 MA ${result.best?.fast}/${result.best?.slow}, 점수 ${result.best?.score}`);
}

function renderPromotionQueue(candidates) {
  const rows = Array.isArray(candidates) ? candidates : [];
  const node = el("#validationPromotionQueue");
  if (!node) return;
  node.innerHTML = rows.length ? `
    <div class="promotion-queue-card">
      <div class="queue-head"><strong>최근 모의투자 후보 큐</strong><span>${rows.length}개 저장됨 · 실제 주문 꺼짐</span></div>
      <div class="queue-list">
        ${rows.slice(0, 8).map((row) => {
          const promo = row.promotion || {};
          const summaries = row.summaries || {};
          const relative = summaries.relative || {};
          const rehearsal = row.paper_rehearsal || null;
          const mark = rehearsal?.mark || {};
          const review = rehearsal?.review || {};
          const rehearsalStatus = rehearsal
            ? `${escapeHtml(koreanStatusText(rehearsal.ticket_status || "기록됨"))} · ${escapeHtml(rehearsal.ticket_id || "-")}`
            : "아직 리허설 없음";
          const rehearsalDetail = rehearsal
            ? `${escapeHtml(rehearsal.created_at || "")} · 현재 ${money(mark.current_price || 0)} · 손익 ${pct(mark.pnl_pct || 0)} · ${escapeHtml(review.label || mark.verdict || "-")}`
            : "모의 준비 후보만 모의 티켓으로 넘길 수 있습니다.";
          return `
            <div class="queue-row ${rehearsal ? "is-rehearsed" : ""}">
              <b>${escapeHtml(symbolDisplayName(row.symbol, row))} MA ${escapeHtml(row.fast || "-")}/${escapeHtml(row.slow || "-")}</b>
              <span>${escapeHtml(promo.label || "-")} · 준비도 ${Number(promo.readiness_score || 0).toFixed(1)}</span>
              <small>${escapeHtml(row.created_at || "")} · 검증수익 ${pct(row.test_return_pct || 0)} · 상대성과 ${Number(relative.relative_score || 0).toFixed(1)}</small>
              <div class="queue-rehearsal ${rehearsal ? "done" : "pending"}">
                <strong>${rehearsal ? "Paper 리허설 완료" : "Paper 리허설 대기"}</strong>
                <span>${rehearsalStatus}</span>
                <small>${rehearsalDetail}</small>
                ${rehearsal ? `<em class="review-badge ${escapeHtml(review.severity || "ok")}">${escapeHtml(review.action || "다음 점검까지 관찰")}</em>` : ""}
              </div>
              <button data-paper-rehearsal="${escapeHtml(row.id || "")}" ${promo.stage === "PAPER_READY" && !rehearsal ? "" : "disabled"}>${rehearsal ? "리허설 기록됨" : "Paper 리허설"}</button>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  ` : `<div class="validation-ok">저장된 모의투자 후보가 아직 없습니다.</div>`;
}

async function loadPromotionCandidates() {
  try {
    const response = await fetch("/api/strategy/promotion-candidates?limit=20");
    const result = await response.json();
    renderPromotionQueue(result.candidates || []);
  } catch (error) {
    addLog(`모의투자 후보 큐 조회 실패: ${error.message}`);
  }
}

function renderPromotionRehearsals(rehearsals) {
  const rows = Array.isArray(rehearsals) ? rehearsals : [];
  const node = el("#validationRehearsalTimeline");
  if (!node) return;
  if (!rows.length) {
    node.innerHTML = `<div class="validation-ok">아직 모의 리허설 이력이 없습니다. 모의 준비 후보를 먼저 리허설로 넘겨보세요.</div>`;
    return;
  }
  const totalPnl = rows.reduce((sum, row) => sum + Number(row.mark?.pnl || 0), 0);
  const avgPnlPct = rows.reduce((sum, row) => sum + Number(row.mark?.pnl_pct || 0), 0) / rows.length;
  node.innerHTML = `
    <div class="rehearsal-board">
      <div class="rehearsal-head">
        <div>
          <strong>Paper 리허설 관찰 타임라인</strong>
          <span>후보가 모의 티켓으로 넘어간 뒤 현재가 기준 성과를 계속 추적합니다.</span>
        </div>
        <div class="rehearsal-actions">
          <div class="rehearsal-summary">
            <b class="${totalPnl >= 0 ? "up" : "down"}">${money(totalPnl)}</b>
            <small>평균 ${pct(avgPnlPct)}</small>
          </div>
          <button data-queue-rehearsal-report="${escapeHtml(rows[0]?.id || "")}">최신 복기 보고 큐</button>
          <button data-queue-rehearsal-digest>전체 요약 보고 큐</button>
          <button data-queue-rehearsal-trend>변화 보고 큐</button>
          <button data-record-rehearsal-snapshot>기억 스냅샷</button>
          <button data-save-rehearsal-obsidian>옵시디언 기억 저장</button>
        </div>
      </div>
      <div class="rehearsal-list">
        ${rows.slice(0, 10).map((row) => {
          const mark = row.mark || {};
          const candidate = row.candidate || {};
          const review = row.review || {};
          const pnlPct = Number(mark.pnl_pct || 0);
          const pnlClass = pnlPct >= 0 ? "up" : "down";
          return `
            <div class="rehearsal-row ${pnlPct >= 0 ? "positive" : "negative"} ${escapeHtml(review.severity || "ok")}">
              <div>
                <strong>${escapeHtml(symbolDisplayName(row.symbol, row))} <span class="${pnlClass}">${pct(pnlPct)}</span></strong>
                <small>${escapeHtml(row.ticket_status || "-")} · ${escapeHtml(row.ticket_id || "-")} · ${escapeHtml(row.created_at || "")}</small>
              </div>
              <div>
                <b>MA ${escapeHtml(candidate.fast || "-")}/${escapeHtml(candidate.slow || "-")}</b>
                <small>${escapeHtml(candidate.promotion?.label || "전략 후보")} · 준비도 ${Number(candidate.promotion?.readiness_score || 0).toFixed(1)}</small>
              </div>
              <div>
                <b>${money(mark.entry_price || 0)} → ${money(mark.current_price || 0)}</b>
                <small>평가손익 <span class="${pnlClass}">${money(mark.pnl || 0)}</span> · ${escapeHtml(mark.verdict || "-")}</small>
              </div>
              <div class="rehearsal-review">
                <strong class="review-badge ${escapeHtml(review.severity || "ok")}">${escapeHtml(review.label || "계속 관찰")}</strong>
                <small>${escapeHtml(review.action || "다음 점검까지 paper 상태를 유지합니다.")}</small>
                <button data-queue-rehearsal-report="${escapeHtml(row.id || "")}">보고 큐</button>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

async function loadPromotionRehearsals() {
  try {
    const response = await fetch("/api/strategy/promotion-rehearsals?limit=20");
    const result = await response.json();
    renderPromotionRehearsals(result.rehearsals || []);
  } catch (error) {
    addLog(`paper 리허설 타임라인 조회 실패: ${error.message}`);
  }
}

function renderMemorySparkline(snapshots) {
  const rows = [...snapshots].reverse();
  const width = 680;
  const height = 160;
  const pad = 20;
  if (!rows.length) return "";
  const avgValues = rows.map((row) => Number(row.avg_pnl_pct || 0));
  const warnValues = rows.map((row) => Number(row.warning_count || 0));
  const minAvg = Math.min(...avgValues, 0);
  const maxAvg = Math.max(...avgValues, 0);
  const warnMax = Math.max(...warnValues, 1);
  const x = (index) => rows.length === 1 ? width / 2 : pad + (index / (rows.length - 1)) * (width - pad * 2);
  const yAvg = (value) => {
    const span = Math.max(1, maxAvg - minAvg);
    return height - pad - ((value - minAvg) / span) * (height - pad * 2);
  };
  const yWarn = (value) => height - pad - (value / warnMax) * (height - pad * 2);
  const avgPath = rows.map((row, index) => `${index ? "L" : "M"} ${x(index).toFixed(1)} ${yAvg(Number(row.avg_pnl_pct || 0)).toFixed(1)}`).join(" ");
  const warnPath = rows.map((row, index) => `${index ? "L" : "M"} ${x(index).toFixed(1)} ${yWarn(Number(row.warning_count || 0)).toFixed(1)}`).join(" ");
  const zeroY = yAvg(0);
  const points = rows.map((row, index) => {
    const avg = Number(row.avg_pnl_pct || 0);
    const warning = Number(row.warning_count || 0);
    const label = `${escapeHtml(row.created_at || row.id || "-")} · 평균 ${pct(avg)} · 경고 ${warning}건`;
    return `<circle cx="${x(index).toFixed(1)}" cy="${yAvg(avg).toFixed(1)}" r="4"><title>${label}</title></circle>`;
  }).join("");
  return `
    <div class="memory-chart-card">
      <div class="memory-chart-head">
        <strong>스냅샷 추세선</strong>
        <span><b class="avg-dot"></b>평균 손익률 <b class="warn-dot"></b>경고 수</span>
      </div>
      <svg class="memory-sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="Paper 리허설 스냅샷 추세">
        <line class="zero-line" x1="${pad}" y1="${zeroY.toFixed(1)}" x2="${width - pad}" y2="${zeroY.toFixed(1)}"></line>
        <path class="warn-line" d="${warnPath}"></path>
        <path class="avg-line" d="${avgPath}"></path>
        ${points}
      </svg>
    </div>
  `;
}

function renderRehearsalObsidianMemory(obsidian = {}) {
  const notes = Array.isArray(obsidian.notes) ? obsidian.notes : [];
  const folder = obsidian.folder || "";
  const latestPath = obsidian.latest_path || "";
  if (!folder && !latestPath && !notes.length) return "";
  return `
    <div class="memory-vault-card">
      <div class="memory-vault-head">
        <div>
          <strong>옵시디언 장기기억 저장소</strong>
          <span>Paper 리허설 복기 노트를 Markdown으로 쌓아 AI가 다음 사이클에서 다시 학습하게 합니다.</span>
        </div>
        <b>${notes.length}개 노트</b>
      </div>
      <div class="memory-vault-paths">
        <div><small>Vault 폴더</small><span>${escapeHtml(folder || "-")}</span></div>
        <div><small>최신 노트</small><span>${escapeHtml(latestPath || "-")}</span></div>
      </div>
      <div class="memory-note-list">
        ${notes.length ? notes.slice(0, 5).map((note) => `
          <div class="memory-note">
            <strong>${escapeHtml(note.name || "-")}</strong>
            <small>${escapeHtml(note.updated_at || "")}</small>
            <span>${escapeHtml(note.path || "")}</span>
          </div>
        `).join("") : `<div class="memory-note empty"><strong>아직 저장된 노트 없음</strong><small>옵시디언 기억 저장을 누르면 latest.md와 날짜별 노트가 생성됩니다.</small></div>`}
      </div>
    </div>
  `;
}

function renderPromotionRehearsalMemory(payload = {}) {
  const node = el("#validationRehearsalMemory");
  if (!node) return;
  const snapshots = Array.isArray(payload.snapshots) ? payload.snapshots : [];
  const trend = payload.trend || {};
  const delta = trend.delta || {};
  const latest = trend.latest || snapshots[0] || {};
  const previous = trend.previous || snapshots[1] || null;
  const changes = Array.isArray(trend.changes) ? trend.changes : [];
  const obsidian = payload.obsidian || {};
  if (!snapshots.length) {
    node.innerHTML = `<div class="validation-ok">아직 리허설 기억 스냅샷이 없습니다. '기억 스냅샷'을 누르거나 오토파일럿 안전 틱을 실행하면 기록됩니다.</div>`;
    return;
  }
  const state = trend.state || "baseline";
  const deltaAvg = Number(delta.avg_pnl_pct || 0);
  const deltaWarning = Number(delta.warning_count || 0);
  node.innerHTML = `
    <div class="rehearsal-memory-board ${escapeHtml(state)}">
      <div class="memory-head">
        <div>
          <strong>Paper 리허설 기억/변화</strong>
          <span>${escapeHtml(trend.message || "스냅샷 변화 분석 대기")}</span>
        </div>
        <div class="memory-score">
          <b class="${deltaAvg >= 0 ? "up" : "down"}">${deltaAvg >= 0 ? "+" : ""}${deltaAvg.toFixed(2)}%p</b>
          <small>${escapeHtml(trend.label || "기준 스냅샷")} · 경고 ${deltaWarning >= 0 ? "+" : ""}${deltaWarning}건</small>
        </div>
      </div>
      <div class="memory-metrics">
        <div><span>${snapshots.length}</span><small>기억 스냅샷</small></div>
        <div><span>${escapeHtml(latest.id || "-")}</span><small>최신 기억</small></div>
        <div><span>${previous ? escapeHtml(previous.id || "-") : "-"}</span><small>이전 기억</small></div>
        <div><span>${money(latest.total_pnl || 0)}</span><small>최신 총손익</small></div>
        <div><span>${pct(latest.avg_pnl_pct || 0)}</span><small>최신 평균</small></div>
      </div>
      ${renderMemorySparkline(snapshots)}
      <div class="memory-change-list">
        ${changes.length ? changes.slice(0, 8).map((item) => {
          const move = Number(item.pnl_delta_pct || 0);
          return `
            <div class="memory-change ${move >= 0 ? "positive" : "negative"}">
              <strong>${escapeHtml(symbolDisplayName(item.symbol, item))} <span class="${move >= 0 ? "up" : "down"}">${move >= 0 ? "+" : ""}${move.toFixed(2)}%p</span></strong>
              <small>${pct(item.previous_pnl_pct || 0)} → ${pct(item.pnl_pct || 0)} · ${escapeHtml(item.previous_review_status || "-")} → ${escapeHtml(item.review_status || "-")}</small>
            </div>
          `;
        }).join("") : `<div class="memory-change stable"><strong>변화 없음</strong><small>아직 종목별 판정/손익 변화가 감지되지 않았습니다.</small></div>`}
      </div>
      <div class="memory-history-list">
        ${snapshots.slice(0, 6).map((row) => `
          <div class="memory-history ${Number(row.warning_count || 0) ? "warning" : "ok"}">
            <strong>${escapeHtml(row.id || "-")}</strong>
            <span>${escapeHtml(row.created_at || "")}</span>
            <small>평균 ${pct(row.avg_pnl_pct || 0)} · 총손익 ${money(row.total_pnl || 0)} · 경고 ${row.warning_count || 0}건 · ${escapeHtml(row.source || "-")}</small>
          </div>
        `).join("")}
      </div>
      ${renderRehearsalObsidianMemory(obsidian)}
    </div>
  `;
}

async function loadPromotionRehearsalMemory() {
  try {
    const [snapshotResponse, obsidianResponse] = await Promise.all([
      fetch("/api/strategy/promotion-rehearsals/snapshots?limit=20"),
      fetch("/api/strategy/promotion-rehearsals/obsidian"),
    ]);
    const result = await snapshotResponse.json();
    const obsidian = await obsidianResponse.json();
    renderPromotionRehearsalMemory({ ...result, obsidian });
  } catch (error) {
    addLog(`paper 리허설 기억 조회 실패: ${error.message}`);
  }
}

async function queuePromotionRehearsalReport(rehearsalId) {
  try {
    const response = await fetch("/api/strategy/promotion-rehearsals/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: rehearsalId || "", source: "ui-rehearsal-timeline" }),
    });
    const result = await response.json();
    if (!response.ok && response.status !== 202) throw new Error(result.error || "복기 보고 큐 등록 실패");
    addLog(`Paper 복기 보고 outbox: ${result.record?.id || result.record?.reason || "-"}`);
    await loadOpsStatus();
    await loadDispatchCenter();
  } catch (error) {
    addLog(`Paper 복기 보고 큐 실패: ${error.message}`);
  }
}

async function queuePromotionRehearsalDigest() {
  try {
    const response = await fetch("/api/strategy/promotion-rehearsals/digest/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 20, source: "ui-rehearsal-digest" }),
    });
    const result = await response.json();
    if (!response.ok && response.status !== 202) throw new Error(result.error || "리허설 요약 보고 큐 등록 실패");
    addLog(`Paper 리허설 종합 요약 outbox: ${result.record?.id || result.record?.reason || "-"} / ${result.digest?.count || 0}건`);
    await loadOpsStatus();
    await loadDispatchCenter();
  } catch (error) {
    addLog(`Paper 리허설 종합 요약 큐 실패: ${error.message}`);
  }
}

async function queuePromotionRehearsalTrend() {
  try {
    const response = await fetch("/api/strategy/promotion-rehearsals/trend/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 20, source: "ui-rehearsal-trend" }),
    });
    const result = await response.json();
    if (!response.ok && response.status !== 202) throw new Error(result.error || "리허설 변화 보고 큐 등록 실패");
    addLog(`Paper 리허설 변화 보고 outbox: ${result.record?.id || result.record?.reason || "-"} / ${result.trend?.label || "-"}`);
    await loadOpsStatus();
    await loadDispatchCenter();
  } catch (error) {
    addLog(`Paper 리허설 변화 보고 큐 실패: ${error.message}`);
  }
}

async function recordPromotionRehearsalSnapshot() {
  try {
    const response = await fetch("/api/strategy/promotion-rehearsals/snapshot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 20, source: "ui-rehearsal-timeline", force: true }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "리허설 스냅샷 기록 실패");
    const record = result.snapshot?.record || {};
    addLog(`Paper 리허설 기억 스냅샷: ${record.id || result.snapshot?.reason || "-"} / ${result.snapshot?.recorded ? "기록" : "변화 없음"}`);
    await loadPromotionRehearsalMemory();
    await loadAutopilot();
  } catch (error) {
    addLog(`Paper 리허설 기억 스냅샷 실패: ${error.message}`);
  }
}

async function savePromotionRehearsalObsidian() {
  try {
    const response = await fetch("/api/strategy/promotion-rehearsals/obsidian", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 20, source: "ui-rehearsal-obsidian", force_snapshot: false }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "옵시디언 기억 저장 실패");
    addLog(`Paper 리허설 옵시디언 기억 저장: ${result.note?.id || "-"} / ${result.note?.path || "-"}`);
    await loadPromotionRehearsalMemory();
    await loadAutopilot();
  } catch (error) {
    addLog(`Paper 리허설 옵시디언 기억 저장 실패: ${error.message}`);
  }
}

async function registerPromotionCandidate() {
  const params = state.lastValidationParams;
  if (!params) {
    addLog("먼저 전략 검증을 실행해야 후보 큐에 등록할 수 있습니다.");
    return;
  }
  const response = await fetch("/api/strategy/promotion-candidates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...params, source: "web-validation-promotion" }),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    addLog(result.error || "모의투자 후보 큐 등록 실패");
    return;
  }
  renderPromotionQueue(result.candidates || []);
  addLog(`${symbolDisplayName(result.record.symbol, result.record)} MA ${result.record.fast}/${result.record.slow} 모의투자 후보 큐 등록 완료`);
}

async function createPromotionPaperRehearsal(candidateId) {
  if (!candidateId) {
    addLog("paper 리허설 후보 ID가 없습니다.");
    return;
  }
  const response = await fetch("/api/strategy/promotion-candidates/paper-rehearsal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: candidateId, quantity: 1 }),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    addLog(result.error || "paper 리허설 티켓 생성 실패");
    return;
  }
  renderPromotionQueue(result.candidates || []);
  await loadPromotionRehearsals();
  await loadPromotionRehearsalMemory();
  await loadOpsStatus();
  await loadPortfolio();
  addLog(`${symbolDisplayName(result.ticket.symbol, result.ticket)} paper 리허설 티켓 생성: ${result.ticket.status}`);
}

async function runRobustness() {
  const activeSymbol = (el("#symbol").value || state.selectedResearchSymbols[0] || "AAPL").toUpperCase();
  const benchmark = /^\d{6}$/.test(activeSymbol) ? "069500" : "SPY";
  const params = new URLSearchParams({
    symbol: activeSymbol,
    benchmark,
    start: el("#startDate").value,
    end: el("#endDate").value,
    fast: el("#fast").value,
    slow: el("#slow").value,
    segments: "6",
  });
  const response = await fetch(`/api/backtest/robustness?${params.toString()}`);
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "강건성 검증 실패");
  const summary = result.summary || {};
  const robustnessName = symbolDisplayName(result.symbol, result);
  const benchmarkName = symbolDisplayName(result.benchmark, { symbol: result.benchmark, name: result.benchmark });
  setText("robustnessSummary", `${robustnessName} vs ${benchmarkName} · ${summary.verdict} · 안정성 ${summary.stability_score}점 · 통과율 ${summary.pass_rate_pct}%`);
  el("#robustnessList").innerHTML = `
    <div class="robustness-score">
      <strong>${summary.verdict}</strong>
      <span>${summary.stability_score}</span>
      <small>안정성 점수 · 평균초과 ${pct(summary.average_excess_pct || 0)}</small>
    </div>
    ${(result.segments || []).map((row) => `
      <div class="robustness-card ${row.passed ? "passed" : "failed"}">
        <strong>${row.index}. ${row.start_date}~${row.end_date}</strong>
        <span class="${Number(row.excess_return_pct) >= 0 ? "up" : "down"}">초과 ${pct(row.excess_return_pct)}</span>
        <small>전략 ${pct(row.strategy_return_pct)} · 보유 ${pct(row.buy_hold_return_pct)} · 벤치 ${pct(row.benchmark_return_pct)} · MDD ${row.max_drawdown_pct}%</small>
      </div>
    `).join("")}
  `;
  addLog(`강건성검증 ${robustnessName}: ${summary.verdict} / ${summary.stability_score}점`);
}

async function runProtections() {
  const activeSymbol = (el("#symbol").value || state.selectedResearchSymbols[0] || "AAPL").toUpperCase();
  const params = new URLSearchParams({
    symbol: activeSymbol,
    start: el("#startDate").value,
    end: el("#endDate").value,
    fast: el("#fast").value,
    slow: el("#slow").value,
  });
  const response = await fetch(`/api/backtest/protected?${params.toString()}`);
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "보호장치 비교 실패");
  const base = result.base || {};
  const protectedResult = result.protected || {};
  const impact = result.impact || {};
  const protectionName = symbolDisplayName(result.symbol, result);
  setText("protectionSummary", `${protectionName} · ${impact.verdict} · 잠금 ${impact.lock_count || 0}회 · 수익차 ${pct(impact.return_delta_pct || 0)} · MDD차 ${pct(impact.drawdown_delta_pct || 0)}`);
  const events = protectedResult.protection_events || [];
  el("#protectionList").innerHTML = `
    <div class="protection-card hero">
      <strong>${impact.verdict || "비교 완료"}</strong>
      <span>잠금 ${impact.lock_count || 0}회</span>
      <small>쿨다운, 손절 가드, 최대낙폭 제한, 저수익 구간 차단을 함께 비교합니다.</small>
    </div>
    <div class="protection-card">
      <strong>기본 전략</strong>
      <span class="${Number(base.total_return_pct || 0) >= 0 ? "up" : "down"}">${pct(base.total_return_pct || 0)}</span>
      <small>MDD ${base.max_drawdown_pct}% · 승률 ${Number(base.trade_quality?.win_rate_pct || 0).toFixed(1)}% · PF ${Number(base.trade_quality?.profit_factor || 0).toFixed(2)}</small>
    </div>
    <div class="protection-card">
      <strong>보호장치 적용</strong>
      <span class="${Number(protectedResult.total_return_pct || 0) >= 0 ? "up" : "down"}">${pct(protectedResult.total_return_pct || 0)}</span>
      <small>MDD ${protectedResult.max_drawdown_pct}% · 승률 ${Number(protectedResult.trade_quality?.win_rate_pct || 0).toFixed(1)}% · PF ${Number(protectedResult.trade_quality?.profit_factor || 0).toFixed(2)}</small>
    </div>
    <div class="protection-card event-list">
      <strong>최근 보호 이벤트</strong>
      ${events.length ? events.slice(-8).map((event) => `<small>${event.day}일: ${event.reason} · ${event.until_day}일까지 잠금</small>`).join("") : "<small>잠금 이벤트 없음</small>"}
    </div>
  `;
  addLog(`보호장치 ${protectionName}: ${impact.verdict} / 잠금 ${impact.lock_count || 0}회`);
}

async function runTranscriptStrategy() {
  const transcript = el("#strategyTranscript").value || "";
  const payload = {
    symbol: el("#symbol").value || state.selectedResearchSymbols[0] || "AAPL",
    start: el("#startDate").value,
    end: el("#endDate").value,
    transcript,
  };
  const response = await fetch("/api/strategy/from-text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "\uc790\ub9c9 \uc804\ub7b5 \uc2e4\ud328");
  drawCompareChart([result]);
  const transcriptName = symbolDisplayName(result.symbol, result);
  setText("strategyChartNote", `${transcriptName} · ${result.strategy.summary} · ${pct(result.total_return_pct)}`);
  renderBacktestRiskGate(result.risk_gate || {});
  setText("finalEquity", `$${money(result.final_equity)}`);
  setText("totalReturn", pct(result.total_return_pct));
  setText("maxDrawdown", `${Number(result.max_drawdown_pct).toFixed(2)}%`);
  setText("tradeCount", result.trade_count);
  renderTradeQuality(result.trade_quality || {});
  const strategy = result.strategy;
  el("#transcriptStrategyResult").innerHTML = `
    <div class="candidate">
      <strong>${strategy.name} <span class="up">${Math.round(Number(strategy.confidence || 0) * 100)}%</span></strong>
      <small>${strategy.summary}</small>
      <small>MA ${strategy.fast}/${strategy.slow} · RSI ${strategy.uses_rsi ? "사용" : "미사용"} · 돌파 ${strategy.uses_breakout ? strategy.breakout_window + "일" : "미사용"}</small>
    </div>
    <div class="candidate">
      <strong>\ubc31\ud14c\uc2a4\ud2b8 \uacb0\uacfc <span class="${Number(result.total_return_pct) >= 0 ? "up" : "down"}">${pct(result.total_return_pct)}</span></strong>
      <small>\ubcf4\uc720 ${pct(result.buy_hold_return_pct)} · \uae30\uc900 MA12/32 ${pct(result.base_strategy_return_pct)}</small>
      <small>MDD ${result.max_drawdown_pct}% · \uc0e4\ud504 ${result.sharpe} · \ub9e4\ub9e4 ${result.trade_count}\ud68c</small>
    </div>
    <div class="candidate">
      <strong>\ucd94\ucd9c \uba54\ubaa8</strong>
      <small>${(strategy.notes || []).join(" ")}</small>
    </div>
  `;
  addLog(`${t.runTranscriptStrategy}: ${transcriptName} ${pct(result.total_return_pct)}`);
}

async function loadPortfolio() {
  const response = await fetch("/api/portfolio");
  const result = await response.json();
  state.lastPortfolio = result;
  const risk = result.risk || {};
  setText("paperEquity", formatKrw(result.equity));
  setText("cash", formatKrw(result.cash));
  setText("marketValue", formatKrw(result.market_value));
  setText("dashEquity", formatKrw(result.equity));
  setText("dashRisk", `${risk.used_orders || 0}/${risk.max_orders || 0}`);
  setText("riskLine", `${t.orderLimit} ${risk.used_orders || 0}/${risk.max_orders || 0} · ${t.positionLimit} ${risk.max_position_pct || 0}%`);
  setText("riskOrders", `${risk.used_orders || 0}/${risk.max_orders || 0}`);
  setText("riskPosition", `${risk.max_position_pct || 0}%`);
  const riskPct = risk.max_orders ? Math.min(100, Math.round(((risk.used_orders || 0) / risk.max_orders) * 100)) : 0;
  setText("dashRiskScore", riskPct >= 70 ? t.riskCaution : t.riskSafe);
  setText("dashOrderUsage", `${riskPct}%`);
  setText("dashPositionCap", `${risk.max_position_pct || 0}%`);
  el("#dashRiskNeedle").style.width = `${Math.max(8, riskPct)}%`;
  const positions = Array.isArray(result.positions) ? result.positions : [];
  const signature = positions.map((position) => `${position.symbol}:${position.quantity}`).join("|") || "empty";
  if (signature !== state.positionSignature) {
    state.positionSignature = signature;
    el("#positions").innerHTML = positions.length
      ? positions.map((position) => `<div class="position"><strong>${escapeHtml(symbolDisplayName(position.symbol, position))}</strong><span>${position.quantity}</span><span>${formatKrw(position.value)}</span></div>`).join("")
      : `<div class="position"><strong>-</strong><span>${t.noPosition}</span><span>-</span></div>`;
  }
  renderPaperLedgerHealth(result.valuation_issue_summary || {});
  renderAccountDashboard();
}

function renderPaperLedgerHealth(issue = {}) {
  const node = el("#paperLedgerHealth");
  if (!node) return;
  const quality = String(issue.quality || "ok").toLowerCase();
  const quarantineCount = Number(issue.quarantined_ticket_count || 0);
  const warningCount = Number(issue.warning_count || 0);
  const groups = Array.isArray(issue.quarantined_groups) ? issue.quarantined_groups.slice(0, 3) : [];
  const unitQueue = Array.isArray(issue.unit_review_queue) ? issue.unit_review_queue.slice(0, 3) : [];
  const decisionSafety = issue.decision_safety || {};
  const plan = Array.isArray(issue.repair_plan) ? issue.repair_plan.slice(0, 2) : [];
  const tone = quality === "watch" || quarantineCount || warningCount ? "watch" : "ok";
  node.className = `paper-ledger-health ${tone}`;
  if (!quarantineCount && !warningCount) {
    node.innerHTML = `
      <div class="paper-ledger-health-head">
        <strong>Paper 원장 정상</strong>
        <span>격리된 가격/통화 기록이 없습니다.</span>
      </div>
      <small>${escapeHtml(issue.safety || "Paper 진단 전용입니다. 실전 주문은 실행하지 않습니다.")}</small>
    `;
    return;
  }
  node.innerHTML = `
    <div class="paper-ledger-health-head">
      <strong>Paper 원장 정리 필요</strong>
      <span>격리 ${quarantineCount.toLocaleString()}건 · 단위검증 ${unitQueue.length.toLocaleString()}개 · 가격/통화 경고 ${warningCount.toLocaleString()}개</span>
    </div>
    <div class="paper-ledger-health-groups">
      ${groups.length ? groups.map((group) => `
        <span>
          <b>${escapeHtml(group.label || group.symbol || "격리 종목")}</b>
          <small>${Number(group.count || 0).toLocaleString()}건 · ${escapeHtml((group.reason_labels || [group.suggested_action || "-"])[0] || "-")}</small>
          ${group.price_unit_review?.suspect ? `<small class="paper-unit-candidates">단위 후보 ${escapeHtml((group.price_unit_review.candidates || []).map((item) => item.display || `x${item.multiplier}`).join(" · ") || "검증 대기")}</small>` : ""}
          <em>${escapeHtml(group.suggested_action || "원본 체결가 단위 복구 전까지 성과 계산에서 제외 유지")}</em>
        </span>
      `).join("") : `<span><b>격리 상세 없음</b><small>${escapeHtml(issue.detail || "원장 진단 정보 대기")}</small></span>`}
    </div>
    ${unitQueue.length ? `
      <div class="paper-unit-review-queue">
        <strong>가격 단위 검증 큐</strong>
        ${unitQueue.map((row) => `
          <small>
            ${escapeHtml(row.label || row.symbol || "검증 대기")}
            · 원시 ${escapeHtml(`${row.raw_price_min ?? "-"}~${row.raw_price_max ?? "-"}`)}
            · 후보 ${escapeHtml((row.candidate_labels || []).join(" · ") || "KRX/KIS 확인 필요")}
          </small>
        `).join("")}
      </div>
    ` : ""}
    ${decisionSafety.status === "guarded" ? `
      <div class="paper-decision-safety">
        <strong>판단 안전장치</strong>
        <small>${escapeHtml(decisionSafety.reason || "격리 기록은 성과와 후보 점수에서 제외됩니다.")}</small>
        <small>제외 ${Number(decisionSafety.excluded_ticket_count || 0).toLocaleString()}건 · 자동보정 ${decisionSafety.auto_repair_allowed ? "허용" : "금지"} · 원장수정 ${decisionSafety.ledger_mutation_allowed ? "허용" : "금지"}</small>
      </div>
    ` : ""}
    <div class="paper-ledger-health-plan">
      ${plan.length ? plan.map((step) => `<small><b>${Number(step.step || 0)}</b> ${escapeHtml(step.title || "-")} · ${escapeHtml(step.detail || "")}</small>`).join("") : `<small>${escapeHtml(issue.next_action || "원장 보정은 별도 audit trail로만 진행합니다.")}</small>`}
    </div>
  `;
}

async function loadJournal() {
  const response = await fetch("/api/journal");
  const result = await response.json();
  state.lastLogs = result.events;
  setText("dashLogCount", `${result.events.length}\uac1c`);
  el("#dashLog").innerHTML = result.events.slice(0, 8).map((event) => `<div class="event"><strong>${event.type}</strong> ${event.message}</div>`).join("") || `<div class="event">${t.waiting}</div>`;
  const eventLog = el("#eventLog");
  if (eventLog) {
    eventLog.innerHTML = result.events.slice(0, 30).map((event) => {
      const stamp = event.time ? new Date(Number(event.time) * 1000).toLocaleTimeString("ko-KR", { hour12: false }) : "-";
      return `<div class="event"><strong>${stamp} · ${event.type}</strong> ${event.message}</div>`;
    }).join("") || `<div class="event">${t.waiting}</div>`;
  }
}

function tradeJournalCount(value) {
  return `${Number(value || 0).toLocaleString("ko-KR")}회`;
}

function tradeJournalSafeText(value) {
  return escapeHtml(replaceSymbolCodesInText(productText(value || "")));
}

function renderTradeJournalSummary(result = {}) {
  const summary = result.summary || {};
  setText("tradeJournalState", result.generated_at ? `${result.today || ""} 기준` : "대기");
  setText("tradeJournalTodayTrain", tradeJournalCount(summary.today_training_units));
  setText("tradeJournalAvgTrain", tradeJournalCount(Math.round(Number(summary.average_training_units_per_full_day || 0))));
  setText("tradeJournalReplayCount", tradeJournalCount(summary.historical_replay_count));
  setText("tradeJournalTicketCount", tradeJournalCount(summary.order_ticket_count));

  const highlights = [];
  const live = result.latest_live_review || {};
  if (live.summary || live.name || live.symbol) {
    const name = live.symbol ? symbolDisplayName(live.symbol, live) : (live.name || "종목");
    highlights.push({
      badge: "실전복기",
      title: `${name} ${formatSignedKrw(live.pnl || 0)} / ${pct(Number(live.pnl_pct || 0))}`,
      meta: live.created_at || "-",
      body: live.summary || "최근 실전 매매 복기를 기록했습니다.",
      foot: Array.isArray(live.next_rules) && live.next_rules.length ? `다음 규칙: ${live.next_rules[0]}` : "",
    });
  }

  const drill = result.latest_daily_drill || {};
  if (drill.id) {
    highlights.push({
      badge: "당일장훈련",
      title: `${drill.target_date || "-"} ${drill.completed_repeats || 0}/${drill.repeats_requested || 0}회 · 평균 ${pct(Number(drill.average_return_pct || 0))}`,
      meta: `총 매매 ${tradeJournalCount(drill.total_trade_count)} · 최고 ${pct(Number(drill.best_return_pct || 0))}`,
      body: `최고: ${drill.best_label || "-"} / 최저: ${drill.worst_label || "-"} ${pct(Number(drill.worst_return_pct || 0))}`,
      foot: drill.lesson || "",
    });
  }

  const replay = result.latest_replay || {};
  if (replay.id || replay.label) {
    highlights.push({
      badge: "과거장",
      title: `${replay.label || "-"} · ${pct(Number(replay.return_pct || 0))}`,
      meta: `${replay.period || "-"} · 매매 ${tradeJournalCount(replay.trade_count)} · MDD ${pct(Number(replay.max_drawdown_pct || 0))}`,
      body: replay.summary || "최신 과거장 리플레이 기록을 저장했습니다.",
      foot: replay.generated_at || "",
    });
  }

  const days = Array.isArray(result.days) ? result.days.slice().reverse().slice(0, 5) : [];
  if (days.length) {
    highlights.push({
      badge: "일별집계",
      title: "최근 훈련량",
      meta: `${days.length}일 표시`,
      body: days.map((day) => `${day.date}: 훈련 ${Number(day.training_units || 0).toLocaleString("ko-KR")}회 / 매매 ${Number(day.trade_count || 0).toLocaleString("ko-KR")}회`).join(" · "),
      foot: "리플레이 1회와 당일장 반복훈련 1회를 각각 훈련 1회로 계산합니다.",
    });
  }

  const node = el("#tradeJournalHighlights");
  if (!node) return;
  node.innerHTML = highlights.length
    ? highlights.map((item) => `
      <div class="worklog-item compact">
        <div><b>${tradeJournalSafeText(item.badge)}</b><strong>${tradeJournalSafeText(item.title)}</strong></div>
        <span>${tradeJournalSafeText(item.meta)}</span>
        <p>${tradeJournalSafeText(item.body)}</p>
        ${item.foot ? `<small>${tradeJournalSafeText(item.foot)}</small>` : ""}
      </div>
    `).join("")
    : `<div class="worklog-item compact"><strong>매매일지 대기</strong><p>훈련이나 실전 복기가 쌓이면 여기에 요약됩니다.</p></div>`;
}

async function loadTradeJournalSummary() {
  const response = await fetch("/api/journal/trade-summary?days=7");
  const result = await response.json();
  if (!response.ok || result.ok === false) throw new Error(result.error || "통합 매매일지를 불러오지 못했습니다.");
  state.lastTradeJournalSummary = result;
  renderTradeJournalSummary(result);
  renderTrainingFlowBoard(result);
  renderDaytradeActionCards();
}

const TRAINING_FLOW_STEPS = [
  { id: "market_scan", phases: ["market_scan", "radar", "market_reflection"], title: "1. 시장 스캔", detail: "시세, 거래대금, 뉴스, 공시, 섹터 흐름을 먼저 봅니다." },
  { id: "candidate", phases: ["candidate", "screener", "backtest"], title: "2. 후보 선별", detail: "점수, 추세, 재무, 리스크 게이트로 오늘 볼 종목을 줄입니다." },
  { id: "paper", phases: ["paper_rehearsal"], title: "3. Paper 리허설", detail: "실전 주문 전 모의 티켓으로 가격, 수량, 중복, 한도를 점검합니다." },
  { id: "replay", phases: ["replay_training"], title: "4. 과거장 훈련", detail: "후보를 과거 데이터에 넣어 수익률, MDD, 승률, 매매일지를 만듭니다." },
  { id: "review", phases: ["market_reflection", "journal"], title: "5. 복기 작성", detail: "잘한 매매와 놓친 매매, 주도 섹터, 다음 규칙을 남깁니다." },
  { id: "memory", phases: ["memory", "capital_challenge"], title: "6. 장기기억 저장", detail: "훈련 결과를 지식망과 장기기억에 저장해 다음 후보 선별에 반영합니다." },
  { id: "meeting", phases: ["staff_meeting"], title: "7. 직원 회의", detail: "연구원과 매매원이 다음 행동, 리스크, 재훈련 대상을 정합니다." },
  { id: "league", phases: ["champion_challenge", "tournament", "internal_league"], title: "8. 리그/왕중왕전", detail: "직원끼리 붙고 챔피언 조건과 비교해 전략을 더 압박합니다." },
];

function currentTrainingPhase() {
  const status = state.lastAgentDaemonStatus || {};
  const task = status.current_task || {};
  const activity = status.current_activity || {};
  return String(task.phase || activity.phase || "").trim();
}

function renderTrainingFlowBoard(result = {}) {
  const node = el("#trainingFlowBoard");
  if (!node) return;
  const phase = currentTrainingPhase();
  const summary = result.summary || state.lastTradeJournalSummary?.summary || {};
  const todayCount = Number(summary.today_training_units || 0);
  const activeIndex = TRAINING_FLOW_STEPS.findIndex((step) => step.phases.includes(phase));
  setText("trainingFlowState", phase ? `현재 단계: ${phase} · 오늘 ${todayCount.toLocaleString("ko-KR")}회` : `자동 루프 기준 · 오늘 ${todayCount.toLocaleString("ko-KR")}회`);
  if (state.lastOpsStatus?.continuous_training) {
    renderContinuousTrainingLoopStatus(state.lastOpsStatus.continuous_training);
  }
  node.innerHTML = TRAINING_FLOW_STEPS.map((step, index) => {
    const stateName = activeIndex < 0
      ? "ready"
      : index < activeIndex
        ? "done"
        : index === activeIndex
          ? "active"
          : "waiting";
    return `
      <article class="training-flow-card ${stateName}" data-step="${escapeHtml(step.id)}">
        <b>${escapeHtml(step.title)}</b>
        <span>${escapeHtml(step.detail)}</span>
      </article>
    `;
  }).join("");
}

function compactReasonList(rows = [], fallback = "장 시작 후 거래대금·상승률·주도테마가 잡히면 표시됩니다.") {
  const list = Array.isArray(rows) ? rows.filter(Boolean).slice(0, 4) : [];
  return list.length
    ? `<ul>${list.map((item) => `<li>${escapeHtml(replaceSymbolCodesInText(String(item)))}</li>`).join("")}</ul>`
    : `<p>${escapeHtml(fallback)}</p>`;
}

function renderDaytradeActionCards() {
  const node = el("#daytradeActionCards");
  if (!node) return;
  const study = state.lastDaytradeStudy || {};
  const weights = study.rule_weights || {};
  const screener = state.lastScreenerResult || {};
  const summary = state.lastTradeJournalSummary || {};
  const candidates = Array.isArray(screener.candidates) ? screener.candidates : [];
  const top = screener.top || candidates[0] || {};
  const topName = top.symbol ? symbolDisplayName(top.symbol, top) : "후보 대기";
  const excludedRows = candidates
    .map((row) => {
      const horizon = row.trade_horizon || {};
      const criteria = horizon.daytrade_criteria || {};
      const risks = Array.isArray(horizon.daytrade_risks) ? horizon.daytrade_risks : [];
      if (criteria.entry_allowed || !risks.length) return null;
      return `${symbolDisplayName(row.symbol, row)}: ${risks.slice(0, 2).join(" · ")}`;
    })
    .filter(Boolean)
    .slice(0, 4);
  const drill = summary.latest_daily_drill || {};
  const checklist = Array.isArray(study.execution_checklist) ? study.execution_checklist.slice(0, 4) : [];
  const studyScore = Number(study.study_score || 0);
  const candidateCount = candidates.length;
  const entryStart = weights.entry_start || "09:30";
  const entryEnd = weights.entry_end || "14:20";
  const amountFilter = Number(weights.small_account_watch_amount_krw || 0) / 100000000;
  const strictAmount = Number(weights.strict_amount_krw || 0) / 100000000;
  const highChase = Number(weights.high_chase_caution_pct || 15);
  setText(
    "daytradeActionState",
    studyScore ? `공부 ${studyScore.toFixed(0)}점 · 후보 ${candidateCount}개 · 최고 ${topName}` : "학습 기준 대기"
  );
  node.innerHTML = [
    {
      tone: "rule",
      title: "오늘 단타 기준",
      meta: `${entryStart}~${entryEnd} · 소액 ${amountFilter ? `${amountFilter.toLocaleString("ko-KR")}억+` : "거래대금 확인"}`,
      body: [
        `정석 거래대금 ${strictAmount ? `${strictAmount.toLocaleString("ko-KR")}억+` : "확인 대기"}`,
        `상승률 ${highChase.toFixed(0)}% 이상은 고점 추격 위험`,
        "주도테마 안 1등/2등 대장주만 후보",
      ],
      foot: checklist[0] || "불개미/홍인기 공개 원칙을 후보 필터에 반영합니다.",
    },
    {
      tone: excludedRows.length ? "warn" : "wait",
      title: "왜 제외됐나",
      meta: top.symbol ? `최고 후보: ${topName} · ${Number(top.score || 0).toFixed(1)}점` : "스크리너 대기",
      bodyHtml: compactReasonList(excludedRows, "아직 제외 사유가 충분히 없습니다. 정규장 데이터가 쌓이면 자동으로 채워집니다."),
      foot: "제외 사유는 실제 주문 차단 이유와 연결해 계속 보강합니다.",
    },
    {
      tone: drill.id ? "train" : "wait",
      title: "장후 10회 훈련",
      meta: drill.id ? `${drill.target_date || "-"} · ${drill.completed_repeats || 0}/${drill.repeats_requested || 10}회` : "최근 훈련 대기",
      body: drill.id
        ? [
            `평균 ${pct(Number(drill.average_return_pct || 0))}`,
            `최고 ${pct(Number(drill.best_return_pct || 0))}`,
            `총 매매 ${tradeJournalCount(drill.total_trade_count)}`,
          ]
        : ["장 마감 후 당일 거래대금 상위와 놓친 대장주를 반복 훈련합니다."],
      foot: drill.lesson || "훈련 결과는 다음 장 후보 필터와 매매일지에 반영됩니다.",
    },
  ].map((card) => `
    <article class="daytrade-action-card ${escapeHtml(card.tone)}">
      <div>
        <b>${escapeHtml(card.title)}</b>
        <span>${escapeHtml(replaceSymbolCodesInText(card.meta || ""))}</span>
      </div>
      ${card.bodyHtml || compactReasonList(card.body || [])}
      <small>${escapeHtml(replaceSymbolCodesInText(card.foot || ""))}</small>
    </article>
  `).join("");
}

async function loadDaytradeActionCards(force = false) {
  const response = await fetch(force ? "/api/agent/daytrade-study?force=1" : "/api/agent/daytrade-study");
  const result = await response.json();
  if (!response.ok || result.ok === false) throw new Error(result.error || "단타 공부 기준을 불러오지 못했습니다.");
  state.lastDaytradeStudy = result;
  renderDaytradeActionCards();
}

async function loadLogic() {
  const response = await fetch("/api/logic");
  const result = await response.json();
  renderLogic(result.slots);
}

function renderLogic(slots) {
  setText("logicCount", `${slots.length}\uac1c`);
  setText("dashLogic", `${slots.length}\uac1c`);
  el("#logicList").innerHTML = slots.map((slot) => `<div class="logic-item"><div><strong>${slot.name}</strong><br><small>MA ${slot.fast}/${slot.slow} · ${slot.memo || "-"}</small></div><span class="badge">${slot.locked ? "\uc7a0\uae08" : "\uc218\uc815"}</span></div>`).join("");
}

async function submitOrder(side) {
  const payload = { symbol: state.active, side, quantity: Number(el("#quantity").value || 0), source: "web-chart-order" };
  const quote = state.quotes.get(state.active) || {};
  const meta = symbolMeta(state.active, quote);
  setText("orderResult", `${meta.name} ${side === "BUY" ? "모의 매수" : "모의 매도"} 기록 전송 중...`);
  const response = await fetch("/api/order", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const result = await response.json();
  if (!response.ok || result.ok === false) {
    setText("orderResult", `주문 실패: ${result.error || "주문 실패"}`);
    return addLog(result.error || "\uc8fc\ubb38 \uc2e4\ud328");
  }
  const status = result.ops_ticket?.status || result.order?.status || "-";
  const sideLabel = result.order.side === "BUY" ? "모의 매수" : "모의 매도";
  setText("orderResult", `${meta.name} ${sideLabel} 기록 완료 · 수량 ${payload.quantity} · 상태 ${status}`);
  addLog(`${symbolDisplayName(result.order.symbol, result.order)} ${sideLabel} ${t.filled} · OPS ${status}`);
  await loadPortfolio();
  await loadOpsStatus();
  await loadJournal();
  renderOrderPreview();
}

function actionLabel(action) {
  if (action === "BUY") return t.buy;
  if (action === "SELL") return t.sell;
  if (action === "WAIT") return t.waiting;
  if (action === "HOLD") return t.hold;
  return action;
}

async function runAutoStrategy() {
  const payload = { symbol: state.active, fast: Number(el("#fast").value || 12), slow: Number(el("#slow").value || 32), quantity: Number(el("#quantity").value || 10) };
  const response = await fetch("/api/strategy/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "\uc790\ub3d9\uc804\ub7b5 \uc2e4\ud328");
  addLog(`${t.auto}: ${actionLabel(result.action)} - ${result.reason}`);
  await loadPortfolio();
  await loadJournal();
}

async function runResearch() {
  setText("researchState", t.running);
  const start = new Date(el("#startDate").value);
  const end = new Date(el("#endDate").value);
  const days = Math.max(120, Math.round((end - start) / 86400000));
  const payload = { symbol: el("#symbol").value || state.active, days };
  const response = await fetch("/api/research/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "\uc804\ub7b5 \uc5f0\uad6c \uc2e4\ud328");
  state.lastCandidates = result.candidates;
  setText("researchState", `${t.done}: ${result.best.name}`);
  renderCandidates(result.candidates);
  el("#fast").value = result.best.fast;
  el("#slow").value = result.best.slow;
  addLog(`${t.research}: ${result.best.name}`);
  await loadJournal();
}

async function runLiveResearch() {
  const response = await fetch("/api/research/live?symbols=005930,000660,005380,035420,051910,006400");
  const result = await response.json();
  const rows = result.rows || [];
  el("#liveResearchList").innerHTML = rows.length
    ? rows.map((row, index) => {
      const actionClass = row.action === t.actionCaution || row.action === "\uc8fc\uc758" ? "down" : row.action === "\uad00\uc2ec" ? "up" : "flat";
      const latest = row.latest_disclosure ? `${row.latest_disclosure.rcept_dt || "-"} ${row.latest_disclosure.report_nm || ""}` : t.dartEmpty;
      const priceLine = row.price_ok ? `${Number(row.price || 0).toLocaleString()}원 ${pct(Number(row.change_pct || 0))}` : row.quote_message || t.dataFail;
      return `<div class="candidate live-research-card">
        <strong>${index + 1}. ${escapeHtml(symbolDisplayName(row.symbol, row))} <span class="${actionClass}">${row.action}</span></strong>
        <small>\uc810\uc218 ${row.score} · DART ${row.dart_count}\uac74 · ${row.dart_stance} · ${priceLine}</small>
        <small>${latest}</small>
      </div>`;
    }).join("")
    : `<div class="event">${t.waiting}</div>`;
  addLog(`${t.liveResearch}: ${rows.length}\uac1c \uc885\ubaa9 \uc2a4\uce94`);
}

function renderBriefRows(target, rows, kind) {
  const node = el(target);
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 8).map((row) => {
      const klass = row.action === "\uc8fc\uc758" ? "down" : row.action === "\uad00\uc2ec" ? "up" : "flat";
      const detail = kind === "kr"
        ? `DART ${row.dart_count}\uac74 · ${row.dart_stance} · ${row.quote_message || ""}`
        : `${Number(row.price || 0).toLocaleString()} · ${pct(Number(row.change_pct || 0))}`;
      return `<div class="event"><strong>${escapeHtml(symbolDisplayName(row.symbol, row))}</strong> <span class="${klass}">${row.action}</span><br><small>${detail}</small></div>`;
    }).join("")
    : `<div class="event">${t.waiting}</div>`;
}

async function loadAiBrief() {
  const response = await fetch("/api/ai-trader/brief");
  const brief = await response.json();
  setText("aiTraderHeadline", brief.headline || "-");
  const kr = brief.markets.kr;
  const us = brief.markets.us;
  setText("aiKrSummary", `\uad00\uc2ec ${kr.watch_count} / \uc8fc\uc758 ${kr.caution_count}`);
  setText("aiUsSummary", `\uad00\uc2ec ${us.watch_count} / \uc8fc\uc758 ${us.caution_count}`);
  renderBriefRows("#aiKrRows", kr.rows || [], "kr");
  renderBriefRows("#aiUsRows", us.rows || [], "us");
  const tg = brief.telegram || {};
  setText("telegramState", tg.configured ? (tg.dry_run ? "\ub4dc\ub77c\uc774\ub7f0" : "\uc5f0\uacb0") : "\ubbf8\uc124\uc815");
  setText("telegramNote", `enabled=${tg.enabled} configured=${tg.configured} dry_run=${tg.dry_run} chat=${tg.chat_masked || "-"}`);
  await loadEconomicSignalReport();
}

function renderPreMarketLineGroup(selector, lines = [], emptyText = "브리핑 대기") {
  const node = el(selector);
  if (!node) return;
  const rows = Array.isArray(lines) ? lines : [];
  node.innerHTML = rows.length
    ? rows.map((line) => `<div class="premarket-line">${escapeHtml(replaceSymbolCodesInText(line))}</div>`).join("")
    : `<div class="premarket-line">${escapeHtml(emptyText)}</div>`;
}

function renderPreMarketBriefing(brief = {}) {
  const market = brief.market || {};
  const source = brief.source || {};
  const generatedAt = brief.generated_at ? shortDateLabel(brief.generated_at) : "-";
  setText("preMarketBriefState", brief.cached ? "캐시" : "최신");
  setText("preMarketBriefHeadline", replaceSymbolCodesInText(brief.headline || "장전 브리핑을 준비하는 중입니다."));
  setText("preMarketBriefSafety", brief.safety || "주문 전송 없음 · 특정 종목 매수 지시 아님");
  const summaryNode = el("#preMarketBriefSummary");
  if (summaryNode) {
    summaryNode.innerHTML = [
      ["생성", generatedAt],
      ["시장 국면", `${market.regime || "-"} · ${Number(market.score || 0).toFixed(1)}/100`],
      ["시장상태", market.session_line || "-"],
      ["뉴스출처", source.overnight || source.sector_news || "-"],
    ].map(([label, value]) => `
      <div>
        <small>${escapeHtml(label)}</small>
        <strong>${escapeHtml(replaceSymbolCodesInText(value))}</strong>
      </div>
    `).join("");
  }
  renderPreMarketLineGroup("#preMarketOvernightLines", brief.overnight_lines || [], "지난밤 이슈 수집 대기");
  renderPreMarketLineGroup("#preMarketNewsLines", brief.news_lines || [], "뉴스 핵심 수집 대기");
  renderPreMarketLineGroup("#preMarketSectorLines", brief.sector_lines || [], "섹터 판단 대기");
  renderPreMarketLineGroup("#preMarketCandidateLines", brief.candidate_lines || [], "후보군 계산 대기");
  renderPreMarketLineGroup("#preMarketRiskLines", brief.risk_lines || [], "위험 신호 대기");
  renderPreMarketLineGroup("#preMarketActionLines", brief.ai_actions || [], "AI 장중 행동계획 대기");
}

async function loadPreMarketBriefing(force = false) {
  setText("preMarketBriefState", force ? "새로 읽는 중" : "조회 중");
  try {
    const response = await fetch(`/api/agent/pre-market-briefing${force ? "?force=1" : ""}`);
    const brief = await response.json();
    if (!response.ok) throw new Error(brief.error || "장전 브리핑 조회 실패");
    state.preMarketBriefing = brief;
    renderPreMarketBriefing(brief);
    if (force) addLog("장전 AI 뉴스 브리핑을 새로 읽었습니다.");
  } catch (error) {
    setText("preMarketBriefState", "실패");
    renderPreMarketLineGroup("#preMarketOvernightLines", [], `장전 브리핑 실패: ${error.message}`);
    addLog(`장전 브리핑 실패: ${error.message}`);
  }
}

async function queuePreMarketBriefing() {
  setText("preMarketBriefState", "텔레그램 큐 등록 중");
  try {
    const response = await fetch("/api/telegram/pre-market-briefing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "ui-pre-market-briefing", force: false }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "장전 브리핑 큐 등록 실패");
    renderPreMarketBriefing(result.brief || state.preMarketBriefing || {});
    setText("preMarketBriefState", result.record?.queued ? "텔레그램 큐 등록" : "정책상 보류");
    addLog(`장전 브리핑 텔레그램 큐: ${result.record?.id || result.record?.status || "-"}`);
    await loadDispatchCenter();
    await loadOpsStatus();
  } catch (error) {
    setText("preMarketBriefState", "큐 등록 실패");
    addLog(`장전 브리핑 텔레그램 큐 실패: ${error.message}`);
  }
}

async function loadEconomicSignalReport() {
  const response = await fetch("/api/quantking/report");
  const report = await response.json();
  setText("economicSignalRegime", `${productText(report.economic.regime)} · ${report.economic.count}\uac1c`);
  el("#economicSignalRows").innerHTML = (report.economic.top_alerts || []).slice(0, 8).map((row) => {
    const klass = row.alert === "\ud558\ub77d" ? "down" : row.alert === "\uc0c1\uc2b9" ? "up" : "flat";
    return `<div class="event"><strong>${productHtml(row.name)}</strong> <span class="${klass}">${productHtml(row.alert)}</span><br><small>${productHtml(row.group)} · ${pct(row.change_pct)} · \ub9ac\uc2a4\ud06c ${row.risk_score}</small></div>`;
  }).join("");
  el("#hedgeStrategyRows").innerHTML = (report.hedge.rows || []).map((row) => `
    <div class="candidate">
      <strong>${productHtml(row.name)} <span class="${row.current_signal === "\ud5f7\uc9d5" ? "down" : "up"}">${productHtml(row.current_signal)}</span></strong>
      <small>${productHtml(row.rule)}</small>
      <small>\ucd5c\uc885 ${row.final_return_pct}% · 08\ub144 ${row.crisis_2008_return_pct}% · \ub9e4\ub9e4 ${row.trade_count}\ud68c</small>
    </div>
  `).join("");
}

async function loadAgentDaemon() {
  try {
    const response = await fetch("/api/agent/daemon");
    const status = await response.json();
    state.lastAgentDaemonStatus = status;
    const memory = status.memory || {};
    const graph = memory.knowledge_graph || {};
    const role = status.role || {};
    const reporting = status.reporting || {};
    const activity = status.current_activity || {};
    setText("aiDaemonState", status.running ? activity.label || "기록·검증 중" : "대기");
    renderAiTrainingToggle(status);
    renderDaemonActivity(status);
    renderDaemonWorkerBoard(status.worker_board || {});
    renderTrainingFlowBoard(state.lastTradeJournalSummary || {});
    setText("daemonCycleCount", `${memory.cycle_count || 0}개`);
    setText("daemonReplayCount", `${memory.historical_replay_memory_count || 0}개`);
    setText("daemonKnowledgeGraph", `${graph.node_count || 0}/${graph.edge_count || 0}`);
    setText("daemonInterval", formatDaemonInterval(status.interval_seconds));
    setText("daemonVault", memory.vault || "-");
    setText("daemonSafety", status.safety || "주문잠금");
    const outputs = Array.isArray(role.outputs) ? role.outputs : [];
    const latestReplay = memory.latest_historical_replay_memory || {};
    const latestCycle = status.last_cycle || memory.last_cycle || {};
    const latestLearning = latestReplay.period
      ? `최근 과거장 훈련 ${latestReplay.period} · 수익 ${pct(latestReplay.return_pct || 0)}`
      : latestCycle.stamp
        ? `최근 사이클 ${latestCycle.stamp} · ${latestCycle.headline || "기록 완료"}`
        : "아직 저장된 학습 기록이 없습니다.";
    setText("daemonRoleName", role.name || "연구 AI 직원");
    setText("daemonRoleMission", role.mission || "후보 발굴, 백테스트, 과거장 훈련, 장기기억 저장을 담당합니다.");
    const scheduledOn = Boolean(reporting.scheduled_reports_enabled);
    const tradeReasonOn = Boolean(reporting.trade_reason_reports_enabled);
    setText("daemonReportMode", reporting.telegram_auto_report ? "연구 자동보고 켜짐" : `${scheduledOn ? "시간표 보고 켜짐" : "시간표 보고 꺼짐"} · ${tradeReasonOn ? "매매사유 켜짐" : "매매사유 꺼짐"}`);
    setText("daemonReportDetail", reporting.detail || "연구 데몬 자동보고는 끄고, 장전/장중/마감/복기/21시와 매매 사유만 보고합니다.");
    setText("daemonOutputTargets", outputs.length ? outputs.join(" · ") : "AgentMemory · Obsidian · KnowledgeGraph");
    setText("daemonLastLearning", latestLearning);
    const candidates = memory.top_candidates || [];
    el("#daemonCandidates").innerHTML = candidates.length
      ? candidates.slice(0, 8).map((item, index) => `
        <div class="daemon-candidate">
          <strong>${index + 1}. ${escapeHtml(symbolDisplayName(item.symbol, item))}</strong>
          <span class="${Number(item.score || 0) >= 70 ? "up" : "flat"}">점수 ${Number(item.score || 0).toFixed(2)}</span>
          <small>${item.market || "-"} · 게이트 ${item.risk_gate_status || "-"} · 수익 ${pct(item.return_pct || 0)} · 승률 ${Number(item.win_rate_pct || 0).toFixed(1)}% · 강건성 ${item.robustness_score || "-"} · ${item.protection_verdict || "-"}</small>
        </div>
      `).join("")
      : `<div class="event">아직 누적된 장기기억 후보가 없습니다. 연구 AI를 켜면 자동보고 없이 후보 발굴, 검증, 과거장 훈련 기록부터 쌓습니다.</div>`;
  } catch (error) {
    setText("aiDaemonState", "상태 조회 실패");
    renderAiTrainingToggle({ running: false, last_error: error.message });
    renderDaemonActivity({ current_activity: { label: "상태 조회 실패", detail: error.message, phase: "error", progress_pct: 0 } });
    renderDaemonWorkerBoard({ error: error.message, workers: [] });
  }
}

function formatActivityTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("ko-KR", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function daemonActivitySummary(status = {}) {
  const activity = status.current_activity || {};
  const task = status.current_task || {};
  const label = task.title || activity.label || (status.running ? "기록학습 중" : "대기");
  const detail = task.detail || activity.detail || (status.running ? "AI가 다음 연구 작업을 준비하고 있습니다." : "24시간 시작을 누르면 후보 발굴과 검증을 시작합니다.");
  const progress = Number(task.progress_pct ?? activity.progress_pct);
  const progressText = Number.isFinite(progress) && progress > 0 ? ` · 진행 ${Math.round(progress)}%` : "";
  const stamp = formatActivityTime(task.updated_at || activity.updated_at);
  const stampText = stamp ? ` · 갱신 ${stamp}` : "";
  const target = task.target && task.target !== "-" ? task.target : activity.symbol_name;
  const focus = target && target !== activity.symbol ? ` · 대상 ${target}` : "";
  return {
    label,
    detail: `${detail}${focus}${progressText}${stampText}`,
    phase: task.phase || activity.phase || (status.running ? "working" : "idle"),
    progress: Number.isFinite(progress) ? Math.max(0, Math.min(100, progress)) : 0,
  };
}

function renderDaemonActivity(status = {}) {
  const summary = daemonActivitySummary(status);
  const taskNode = el("#daemonCurrentTask");
  const detailNode = el("#daemonCurrentDetail");
  if (taskNode) {
    taskNode.textContent = `현재 작업: ${summary.label}`;
    taskNode.dataset.phase = summary.phase;
    taskNode.style.setProperty("--activity-progress", `${summary.progress}%`);
  }
  if (detailNode) detailNode.textContent = summary.detail;
}

function workerStatusView(worker = {}) {
  const labels = {
    working: "작업 중",
    monitoring: "상시 감시",
    waiting: "대기",
    blocked: "차단 중",
    stale: "근거 갱신 필요",
    error: "오류",
  };
  const code = String(worker.status_code || "waiting");
  const tone = worker.tone || ({ working: "active", monitoring: "safe", blocked: "danger", stale: "warning", error: "danger" }[code] || "idle");
  const evidenceTime = formatActivityTime(worker.last_evidence_at || worker.updated_at);
  const checkedTime = formatActivityTime(worker.status_checked_at);
  const thresholdSeconds = Number(worker.evidence_threshold_seconds || 0);
  const thresholdText = thresholdSeconds > 0
    ? thresholdSeconds >= 3600
      ? `허용 ${Math.round(thresholdSeconds / 3600)}시간`
      : `허용 ${Math.round(thresholdSeconds / 60)}분`
    : "";
  const eligibilityText = worker.decision_role
    ? worker.decision_eligible ? "판단 가능" : "판단 제외"
    : "";
  const freshness = worker.freshness_label || (evidenceTime ? "근거 확인" : "근거 없음");
  const evidenceParts = [freshness, evidenceTime, thresholdText, eligibilityText].filter(Boolean);
  return {
    code,
    tone,
    label: worker.status_label || labels[code] || worker.state || "대기",
    evidenceText: evidenceParts.join(" · "),
    checkedText: checkedTime ? `상태 확인 ${checkedTime}` : "상태 확인 중",
    progressMode: worker.progress_mode || "idle",
  };
}

function renderDaemonWorkerBoard(board = {}) {
  const node = el("#daemonWorkerBoard");
  if (!node) return;
  const workers = Array.isArray(board.workers) ? board.workers : [];
  const stamp = formatActivityTime(board.generated_at);
  setText("daemonWorkerBoardStamp", board.error ? `조회 실패 · ${board.error}` : stamp ? `갱신 ${stamp}` : "상태 확인 중");
  node.innerHTML = workers.length
    ? workers.map((worker) => {
      const progress = Math.max(0, Math.min(100, Number(worker.progress_pct || 0)));
      const status = workerStatusView(worker);
      const focusItems = Array.isArray(worker.focus_items) ? worker.focus_items : [];
      const progressHtml = status.progressMode === "continuous"
        ? `<div class="daemon-worker-progress continuous"><i></i><span>상시 감시</span></div>`
        : status.progressMode === "task"
          ? `<div class="daemon-worker-progress" style="--worker-progress:${progress}%"><i></i><span>${Math.round(progress)}%</span></div>`
          : `<div class="daemon-worker-progress idle"><i></i><span>대기</span></div>`;
      return `
        <article class="daemon-worker-card ${escapeHtml(status.tone)}" data-worker-status="${escapeHtml(status.code)}">
          <div class="daemon-worker-top">
            <strong>${escapeHtml(worker.name || "AI 직원")}</strong>
            <span>${escapeHtml(status.label)}</span>
          </div>
          <small>${escapeHtml(worker.role || "-")}</small>
          <b>${escapeHtml(worker.task || "작업 대기")}</b>
          <p>${escapeHtml(worker.detail || "현재 세부 작업을 확인 중입니다.")}</p>
          ${focusItems.length ? `
            <div class="daemon-worker-focus">
              ${focusItems.slice(0, 6).map((item) => `
                <span class="${escapeHtml(item.tone || "idle")}">
                  <small>${escapeHtml(item.label || "-")}</small>
                  <b>${escapeHtml(String(item.value ?? "-"))}</b>
                  <em>${escapeHtml(item.detail || "")}</em>
                </span>
              `).join("")}
            </div>
          ` : ""}
          ${progressHtml}
          <dl>
            <div><dt>대상</dt><dd>${escapeHtml(worker.target || "-")}</dd></div>
            <div><dt>근거</dt><dd>${escapeHtml(worker.evidence || "-")}</dd></div>
            <div><dt>다음 행동</dt><dd>${escapeHtml(worker.next_action || "-")}</dd></div>
          </dl>
          <em>${escapeHtml(status.evidenceText)} · ${escapeHtml(status.checkedText)}</em>
        </article>
      `;
    }).join("")
    : `<div class="event">${escapeHtml(board.error || "AI 직원 작업판을 불러오는 중입니다.")}</div>`;
}

function renderAiTrainingToggle(status = {}) {
  const button = el("#aiTrainingToggle");
  if (!button) return;
  const running = Boolean(status.running);
  const reporting = status.reporting || {};
  const reportLabel = reporting.scheduled_reports_enabled ? "시간표 보고 켜짐" : reporting.telegram_auto_report ? "보고 켜짐" : "보고 꺼짐";
  const activity = daemonActivitySummary(status);
  button.dataset.running = running ? "true" : "false";
  setText("aiTrainingToggleText", running ? "연구 AI 기록학습 중" : "연구 AI 대기");
  setText("aiTrainingToggleSub", running ? `${formatDaemonInterval(status.interval_seconds)} · ${reportLabel} · ${activity.label}` : "기록학습 꺼짐");
}

function renderContinuousTrainingLoopStatus(continuous = {}) {
  const loop = continuous.loop || {};
  const bridge = continuous.memory_bridge || {};
  const headline = loop.headline || bridge.headline || "";
  const bridgeText = bridge.needs_decision_context_refresh
    ? "훈련 메모리 후보판단 갱신 필요"
    : bridge.headline || "";
  const flowText = [
    headline || "연속훈련 상태 확인 중",
    bridge.status ? `메모리 ${bridge.status}` : "",
  ].filter(Boolean).join(" · ");
  setText("trainingFlowState", flowText);

  const button = el("#aiTrainingToggle");
  if (!button) return;
  const canStart = loop.can_start !== false;
  button.dataset.loopState = loop.running ? "running" : canStart ? "idle" : "blocked";
  if (button.dataset.running === "true") return;
  const title = loop.running
    ? "연구 AI 훈련 중"
    : canStart
      ? "연구 AI 대기 가능"
      : "연구 AI 보호 대기";
  setText("aiTrainingToggleText", title);
  setText("aiTrainingToggleSub", bridgeText || headline || "훈련 루프 상태 확인 중");
}

function formatDaemonInterval(seconds) {
  const value = Number(seconds || 0);
  if (value <= 10) return "연속";
  if (value < 60) return `${Math.round(value)}초`;
  return `${Math.round(value / 60)}분`;
}

async function toggleAiTraining() {
  const button = el("#aiTrainingToggle");
  const running = button?.dataset.running === "true";
  try {
    setText("aiTrainingToggleText", running ? "정지 중" : "연구원 호출 중");
    const daemonPath = running ? "/api/agent/daemon/stop" : "/api/agent/daemon/start";
    const autoPath = running ? "/api/agent/autopilot/stop" : "/api/agent/autopilot/start";
    const payload = running ? { source: "top-training-toggle" } : { source: "top-training-toggle", interval_seconds: 10 };
    const daemonResponse = await fetch(daemonPath, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const daemonStatus = await daemonResponse.json();
    if (!daemonResponse.ok) throw new Error(daemonStatus.error || "AI 훈련 전환 실패");
    await fetch(autoPath, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).catch(() => null);
    renderAiTrainingToggle(daemonStatus);
    await loadAgentDaemon();
    await loadMission();
    await loadAiStaff();
    addLog(running ? "연구 AI 기록학습 루프를 정지했습니다. 기존 장기기억은 유지됩니다." : "연구 AI 기록학습 루프를 시작했습니다. 자동보고 없이 백테스트, 과거장 훈련, 장기기억을 계속 쌓습니다.");
  } catch (error) {
    renderAiTrainingToggle({ running });
    addLog(`AI 훈련 전환 실패: ${error.message}`);
  }
}

function renderAiStaffRows(selector, rows = [], emptyText = "대기 중") {
  const node = el(selector);
  if (!node) return;
  const knowledgeLabels = {
    research_cycles: "연구",
    historical_replays: "과거장",
    unique_replay_contexts: "고유조건",
    duplicate_replay_contexts: "중복",
    replay_duplicate_pct: "중복률",
    replay_breadth_status: "학습범위",
    paper_rehearsals: "Paper",
    market_reflections: "시장복기",
    knowledge_nodes: "지식노드",
    knowledge_edges: "지식연결",
    broker_execution_checks: "체결점검",
    account_change_checks: "계좌점검",
    live_submitted_today: "오늘제출",
    blocked_or_failed_today: "오늘차단",
    pending_approval_checks: "승인점검",
    minute_market_checks: "분봉점검",
    queued_reports: "보고대기",
  };
  const knowledgeStatusLabels = {
    no_evidence: "근거 없음",
    very_narrow: "매우 좁음",
    narrow: "좁음",
    diversifying: "확장 중",
    broad: "넓음",
  };
  const knowledgeLine = (row = {}) => Object.entries(row.knowledge_evidence || {})
    .filter(([key]) => key !== "updated_at" && knowledgeLabels[key])
    .map(([key, value]) => {
      const display = key === "replay_duplicate_pct"
        ? `${Number(value || 0).toFixed(1)}%`
        : key === "replay_breadth_status"
          ? knowledgeStatusLabels[value] || value
          : Number.isFinite(Number(value)) ? Number(value).toLocaleString() : value;
      return `${knowledgeLabels[key]} ${display}`;
    })
    .join(" · ");
  node.innerHTML = rows.length
    ? rows.map((row) => {
      const knowledge = knowledgeLine(row);
      const status = workerStatusView(row);
      return `
      <div class="ai-staff-card ${escapeHtml(status.tone)}" data-worker-status="${escapeHtml(status.code)}">
        <strong>${escapeHtml(row.name || row.speaker || "-")} <em>${escapeHtml(status.label)}</em></strong>
        <span>${escapeHtml(row.role || row.stance || row.task || "-")}</span>
        ${row.task ? `<small>현재: ${escapeHtml(row.task)}</small>` : ""}
        <small>${escapeHtml(row.message || row.detail || row.default_model || "")}</small>
        ${row.target ? `<small>대상: ${escapeHtml(row.target)}</small>` : ""}
        ${row.evidence ? `<small>근거: ${escapeHtml(row.evidence)}</small>` : ""}
        <small>근거 상태: ${escapeHtml(status.evidenceText)}</small>
        ${knowledge ? `<small>지식근거: ${escapeHtml(knowledge)}</small>` : ""}
        ${row.model ? `<small>모델: ${escapeHtml(row.model)}</small>` : ""}
      </div>
    `;
    }).join("")
    : `<div class="ai-staff-card"><strong>${emptyText}</strong><small>AI 직원 상태를 불러오는 중입니다.</small></div>`;
}

function renderAiStaffMeetingSplit(manualResult = {}, autoResult = {}) {
  const node = el("#aiStaffMeetingSplit");
  if (!node) return;
  const buildCard = (title, result, fallback) => {
    const latest = result.latest || {};
    const top = latest.top_candidate || {};
    const decision = latest.decision || {};
    const quality = latest.dialogue_quality || {};
    const note = latest.note || {};
    const count = Number(result.count || 0);
    const real = latest.real_execution || "-";
    const qualityScore = quality.score !== undefined ? `${Number(quality.score || 0).toFixed(0)}점` : "품질 대기";
    const qualityMode = quality.mode || "구조화 대기";
    const monologueRatio = quality.monologue_ratio !== undefined ? `독백비율 ${Number(quality.monologue_ratio || 0).toFixed(2)}` : "독백비율 -";
    if (!count) {
      return `
        <article class="ai-staff-split-card empty">
          <strong>${escapeHtml(title)}</strong>
          <span>기록 없음</span>
          <small>${escapeHtml(fallback)}</small>
        </article>
      `;
    }
    return `
      <article class="ai-staff-split-card">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(top.name || top.symbol || "후보 없음")} · ${escapeHtml(decision.label || "결론 대기")}</span>
        <small>점수 ${escapeHtml(String(top.score ?? "-"))} · 주문 ${escapeHtml(koreanStatusText(real))}</small>
        <small>회의품질 ${escapeHtml(qualityScore)} · ${escapeHtml(qualityMode)} · ${escapeHtml(monologueRatio)}</small>
        <small>${escapeHtml(latest.created_at || "-")} · ${escapeHtml(note.source_group || latest.source || "-")} · ${count}건</small>
      </article>
    `;
  };
  node.innerHTML = [
    buildCard("수동/빠른 회의", manualResult, "버튼으로 실행한 빠른 회의가 여기에 따로 남습니다."),
    buildCard("자동 직원 회의", autoResult, "백그라운드 AI 직원 회의가 여기에 따로 남습니다."),
  ].join("");
}

async function loadAiStaffMeetingSplit(force = false) {
  const node = el("#aiStaffMeetingSplit");
  if (!node) return;
  const now = Date.now();
  if (!force && state.aiStaffMeetingSplitLoadedAt && now - state.aiStaffMeetingSplitLoadedAt < 120000) return;
  try {
    const [manualResponse, autoResponse] = await Promise.all([
      fetch("/api/agent/staff/meetings?group=manual&quick=1&limit=3"),
      fetch("/api/agent/staff/meetings?group=auto&limit=3"),
    ]);
    const [manualResult, autoResult] = await Promise.all([manualResponse.json(), autoResponse.json()]);
    if (!manualResponse.ok) throw new Error(manualResult.error || "수동 회의 조회 실패");
    if (!autoResponse.ok) throw new Error(autoResult.error || "자동 회의 조회 실패");
    renderAiStaffMeetingSplit(manualResult, autoResult);
    state.aiStaffMeetingSplitLoadedAt = Date.now();
  } catch (error) {
    node.innerHTML = `
      <article class="ai-staff-split-card empty">
        <strong>회의 분리 조회 실패</strong>
        <span>${escapeHtml(error.message)}</span>
        <small>다음 새로고침 때 다시 확인합니다.</small>
      </article>
    `;
  }
}

async function runQuickStaffMeeting() {
  const button = el("#runQuickStaffMeeting");
  const stateNode = el("#quickStaffMeetingState");
  const startedAt = performance.now();
  if (button) button.disabled = true;
  setText("quickStaffMeetingState", "회의 실행 중");
  try {
    const response = await fetch("/api/agent/staff/meeting/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "web-quick-staff-meeting", quick: true }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "빠른 회의 실행 실패");
    await loadAiStaffMeetingSplit(true);
    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(1);
    const top = result.meeting?.top_candidate || {};
    setText("quickStaffMeetingState", `${top.name || top.symbol || "후보"} · ${elapsed}초`);
    addLog(`빠른 AI 직원 회의 완료: ${top.name || top.symbol || "후보 없음"} / ${koreanStatusText(result.meeting?.real_execution || "BLOCKED")}`);
  } catch (error) {
    setText("quickStaffMeetingState", `실패 · ${error.message}`);
    addLog(`빠른 AI 직원 회의 실패: ${error.message}`);
  } finally {
    if (button) button.disabled = false;
    if (stateNode) window.setTimeout(() => {
      if (stateNode.textContent && !stateNode.textContent.startsWith("실패")) setText("quickStaffMeetingState", "대기");
    }, 120000);
  }
}

function renderOhlcvChallengeCard(result = {}) {
  const node = el("#ohlcvChallengeCard");
  if (!node) return;
  if (!result.ok) {
    node.innerHTML = `
      <div class="ohlcv-research-head">
        <strong>심층 워크포워드 연구</strong>
        <span>대기</span>
      </div>
      <p>${escapeHtml(result.verification_message || result.message || "OHLCV 결과의 전체 거래원장 검증을 기다리고 있습니다.")}</p>
    `;
    return;
  }
  const best = result.best || {};
  const top = Array.isArray(result.top) ? result.top : [];
  node.innerHTML = `
    <div class="ohlcv-research-head">
      <strong>심층 워크포워드 연구</strong>
      <span>${escapeHtml(result.generated_at || "-")}</span>
    </div>
    <div class="ohlcv-research-metrics">
      <div><b>${Number(best.multiple || 0).toFixed(4)}배</b><small>최고 복리</small></div>
      <div><b>${money0(best.final_equity || 0)}원</b><small>최종자산</small></div>
      <div><b>${Number(best.max_drawdown_pct || 0).toFixed(2)}%</b><small>MDD</small></div>
      <div><b>${Number(result.tested || 0).toLocaleString()}개</b><small>전략 조합</small></div>
    </div>
    <p>${escapeHtml(result.message || "")}</p>
    <div class="ohlcv-research-list">
      ${top.slice(0, 3).map((row, index) => `
        <div>
          <span>${index + 1}. ${escapeHtml(row.name || "-")}</span>
          <small>${Number(row.multiple || 0).toFixed(4)}배 · MDD ${Number(row.max_drawdown_pct || 0).toFixed(2)}% · 승률 ${Number(row.win_rate_pct || 0).toFixed(2)}%</small>
        </div>
      `).join("")}
    </div>
  `;
}

function renderSmallAccountGrowth(plan = {}) {
  const root = el("#smallAccountGrowthCard");
  if (!root) return;
  const account = plan.account || {};
  const accountMath = plan.account_math || {};
  const limits = plan.limits || {};
  const holdings = Array.isArray(plan.holding_reviews) ? plan.holding_reviews : [];
  const candidates = Array.isArray(plan.buy_candidates) ? plan.buy_candidates : [];
  const watchCandidates = Array.isArray(plan.watch_candidates) ? plan.watch_candidates : [];
  const learning = plan.learning || {};
  const daytradeStudy = plan.daytrader_study || learning.daytrader_study || {};
  const daytradeScout = plan.daytrade_scout || {};
  const daytradeScoutValidation = plan.daytrade_scout_validation || {};
  const positionExitPlan = plan.position_exit_plan || {};
  const executionGate = plan.execution_gate || {};
  const reportSchedule = plan.report_schedule || {};
  const currentTask = plan.current_ai_task || {};
  const scoutItems = Array.isArray(daytradeScout.items) ? daytradeScout.items : [];
  const nextActions = Array.isArray(plan.next_ai_actions) ? plan.next_ai_actions : [];
  const nextActionItems = Array.isArray(plan.next_ai_action_items) && plan.next_ai_action_items.length
    ? plan.next_ai_action_items
    : nextActions.map((action) => ({ owner: "AI 직원", priority: "보통", status: "대기", target: "-", action }));
  const workerFocus = Array.isArray(plan.ai_worker_focus) ? plan.ai_worker_focus : [];
  const planGeneratedAt = plan.generated_at || "";
  const planStateLabel = plan.cached ? "캐시" : plan.ok ? "갱신됨" : "대기";
  const planFreshness = smallAccountFreshness(planGeneratedAt);
  const stateNode = el("#smallAccountState");
  if (stateNode) {
    stateNode.innerHTML = planGeneratedAt
      ? `${escapeHtml(planStateLabel)} · ${escapeHtml(formatDateTimeShort(planGeneratedAt))} · <em data-relative-age-at="${escapeHtml(planGeneratedAt)}">${escapeHtml(formatRelativeAge(planGeneratedAt))}</em> · <b class="freshness-pill" data-freshness-at="${escapeHtml(planGeneratedAt)}" data-freshness-level="${escapeHtml(planFreshness.level)}">${escapeHtml(planFreshness.label)}</b>`
      : escapeHtml(planStateLabel);
  }
  const refreshStatusNode = el("#smallAccountRefreshStatus");
  if (refreshStatusNode && !isSmallAccountRefreshPinned(refreshStatusNode)) {
    refreshStatusNode.dataset.status = plan.ok ? "done" : "idle";
    refreshStatusNode.textContent = plan.ok ? `최근 판단 · ${currentTask.target || "대기"}` : "재확인 대기";
  }
  setText("smallAccountEquity", formatKrw(account.equity || 0));
  setText("smallAccountCash", formatKrw(account.available_cash || 0));
  setText("smallAccountLimit", formatKrw(limits.max_buy_notional || 0));
  setText("smallAccountStop", formatKrw(limits.daily_loss_stop_krw || 0));
  const mathNode = el("#smallAccountMath");
  if (mathNode) {
    const afterTicket = accountMath.after_ticket || {};
    const gapValue = Number(accountMath.gap || 0);
    mathNode.innerHTML = accountMath.formula ? `
      <div class="small-account-math-head">
        <strong>계좌 산식</strong>
        <b class="${Math.abs(gapValue) <= 1000 ? "ok" : "warn"}">${escapeHtml(accountMath.status || "확인")}</b>
      </div>
      <div class="small-account-math-formula">
        <span>현금 ${formatKrw(accountMath.cash || 0)}</span>
        <span>+</span>
        <span>주식평가 ${formatKrw(accountMath.stock_value || 0)}</span>
        <span>=</span>
        <strong>${formatKrw(accountMath.computed_equity || 0)}</strong>
      </div>
      <small>계좌표시 ${formatKrw(accountMath.reported_equity || 0)} · 차이 ${formatKrw(accountMath.gap || 0)}</small>
      <div class="small-account-math-after">
        <b>준비 티켓 반영 후</b>
        <span>현금 ${formatKrw(afterTicket.cash || 0)}</span>
        <span>주식평가 ${formatKrw(afterTicket.stock_value || 0)}</span>
        <span>추정 ${formatKrw(afterTicket.computed_equity || 0)}</span>
      </div>
      <small>${escapeHtml(accountMath.explanation || "증권사 산식과 단순 합계는 조금 다를 수 있습니다.")}</small>
    ` : `<div class="small-account-math-head"><strong>계좌 산식 대기</strong><b class="warn">계산 중</b></div>`;
  }
  const gateNode = el("#smallAccountExecutionGate");
  if (gateNode) {
    const gateChecks = Array.isArray(executionGate.checks) ? executionGate.checks : [];
    const gateBlockReasons = Array.isArray(executionGate.block_reasons) ? executionGate.block_reasons : [];
    const gateWarnings = Array.isArray(executionGate.warnings) ? executionGate.warnings : [];
    const gateRunbook = Array.isArray(executionGate.next_trigger_plan) ? executionGate.next_trigger_plan : [];
    const preparedTicket = executionGate.prepared_ticket || {};
    const ticketImpact = preparedTicket.impact_preview || {};
    const ticketCost = ticketImpact.cost_preview || {};
    const ticketDuplicateGuard = preparedTicket.duplicate_guard || executionGate.duplicate_guard || {};
    const gateTarget = executionGate.target_name || executionGate.target_symbol || "후보 대기";
    const gateSide = executionGate.target_side || "WAIT";
    const gateNextAt = executionGate.next_event_at || positionExitPlan.next_event_at || "";
    const dataFreshness = executionGate.data_freshness || {};
    const freshnessChecks = Array.isArray(dataFreshness.checks) ? dataFreshness.checks : [];
    const freshnessWarningClass = dataFreshness.regular_open && dataFreshness.gate_ok ? "ok" : "warn";
    gateNode.innerHTML = `
      <div class="small-account-gate-head">
        <div>
          <strong>실전 게이트</strong>
          <span>${escapeHtml(gateTarget)} · ${escapeHtml(gateSide)}</span>
        </div>
        <b class="${executionGate.ready ? "ready" : "blocked"}">${escapeHtml(executionGate.state || "대기")}</b>
      </div>
      <p>${escapeHtml(executionGate.summary || "실전 주문 가능 조건을 계산하는 중입니다.")}</p>
      <div class="small-account-gate-meta">
        <span>${escapeHtml(executionGate.phase_label || positionExitPlan.phase_label || "-")}</span>
        <span>${escapeHtml(executionGate.next_event || positionExitPlan.next_event || "-")}</span>
        <span data-countdown-at="${escapeHtml(gateNextAt)}" data-countdown-minutes="${escapeHtml(String(executionGate.minutes_to_next ?? positionExitPlan.minutes_to_next ?? ""))}">${escapeHtml(formatEventCountdown(gateNextAt, executionGate.minutes_to_next ?? positionExitPlan.minutes_to_next))}</span>
      </div>
      ${(dataFreshness.generated_at || freshnessChecks.length) ? `
        <div class="small-account-gate-freshness">
          <div>
            <strong>데이터 신선도</strong>
            <span data-relative-age-at="${escapeHtml(dataFreshness.generated_at || "")}">${escapeHtml(dataFreshness.generated_at ? formatRelativeAge(dataFreshness.generated_at) : "점검 대기")}</span>
          </div>
          <small>계좌 ${escapeHtml(dataFreshness.account_source || "-")} · ${escapeHtml(dataFreshness.account_updated_at ? formatDateTimeShort(dataFreshness.account_updated_at) : "-")}</small>
          <small>가격 ${escapeHtml(dataFreshness.quote_source || "-")} · ${escapeHtml(dataFreshness.price_basis || "-")} · ${escapeHtml(dataFreshness.quote_updated_at ? formatDateTimeShort(dataFreshness.quote_updated_at) : "-")}</small>
          <small class="${freshnessWarningClass}">${escapeHtml(dataFreshness.warning || "주문 전 계좌·가격을 다시 확인합니다.")}</small>
          ${freshnessChecks.length ? `
            <div class="small-account-gate-freshness-grid">
              ${freshnessChecks.slice(0, 3).map((check) => `
                <span><b>${escapeHtml(check.label || "-")}</b>${escapeHtml(check.status || "-")} · ${escapeHtml(check.detail || "-")}</span>
              `).join("")}
            </div>
          ` : ""}
        </div>
      ` : ""}
      ${gateBlockReasons.length ? `
        <div class="small-account-gate-blockers">
          <strong>지금 막힌 조건</strong>
          ${gateBlockReasons.slice(0, 3).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
        </div>
      ` : ""}
      ${preparedTicket.name ? `
        <div class="small-account-gate-ticket">
          <div>
            <strong>준비 티켓</strong>
            <span>${escapeHtml(preparedTicket.guard || "아직 주문 아님")}</span>
          </div>
          <b>${escapeHtml(preparedTicket.name || "-")} · ${escapeHtml(preparedTicket.side || "-")} ${Number(preparedTicket.quantity || 0).toFixed(Number(preparedTicket.quantity || 0) % 1 ? 1 : 0)}주</b>
          <small>티켓 ${escapeHtml(preparedTicket.ticket_id || "-")} · 만료 ${escapeHtml(preparedTicket.expires_at ? formatDateTimeShort(preparedTicket.expires_at) : "-")} · 멱등키 ${escapeHtml(preparedTicket.idempotency_key || "-")}</small>
          ${ticketDuplicateGuard.status ? `<small class="${ticketDuplicateGuard.ok ? "ok" : "warn"}">중복 가드 ${escapeHtml(ticketDuplicateGuard.status || "-")} · 오늘 동일 제출 ${Number(ticketDuplicateGuard.today_submitted_count || 0)}건 · ${escapeHtml(ticketDuplicateGuard.detail || "-")}</small>` : ""}
          <small>예상가 ${formatKrw(preparedTicket.estimated_price || 0)} · 예상금액 ${formatKrw(preparedTicket.estimated_notional || 0)} · ${escapeHtml(preparedTicket.order_type || "-")}</small>
          <small>${escapeHtml(preparedTicket.decision || "-")} · ${escapeHtml(preparedTicket.risk_line || "-")}</small>
          ${ticketImpact.mode ? `
            <div class="small-account-gate-impact">
              <span>현금 ${formatKrw(ticketImpact.cash_before || 0)} → ${formatKrw(ticketImpact.cash_after || 0)}</span>
              <span>주식평가 ${formatKrw(ticketImpact.stock_value_before || 0)} → ${formatKrw(ticketImpact.stock_value_after || 0)}</span>
              <span>추정손익 ${formatKrw(ticketImpact.estimated_pnl || 0)} · ${pct(ticketImpact.estimated_pnl_pct || 0)}</span>
              <span>추정비용 ${formatKrw(ticketCost.total_cost || 0)} · 수수료 ${formatKrw(ticketCost.broker_fee || 0)} · 세금 ${formatKrw(ticketCost.transaction_tax || 0)}</span>
            </div>
          ` : ""}
          <p>${escapeHtml(preparedTicket.reason || "다음 장에서 재확인합니다.")}</p>
        </div>
      ` : ""}
      ${gateRunbook.length ? `
        <div class="small-account-gate-runbook">
          <strong>다음 실행 루틴</strong>
          ${gateRunbook.slice(0, 4).map((item, index) => `
            <div><b>${index + 1}</b><span>${escapeHtml(item)}</span></div>
          `).join("")}
        </div>
      ` : ""}
      <div class="small-account-gate-checks">
        ${gateChecks.length
          ? gateChecks.map((check) => {
            const klass = check.ok ? "pass" : check.severity === "warn" ? "warn" : "block";
            return `
              <div class="small-account-gate-check ${klass}">
                <b>${escapeHtml(check.label || "-")}</b>
                <span>${escapeHtml(check.state || "-")}</span>
                <small>${escapeHtml(check.detail || "-")}</small>
              </div>
            `;
          }).join("")
          : `<div class="small-account-gate-check empty"><b>점검 대기</b><span>계산 중</span><small>계좌·정책·시장 상태를 불러오는 중입니다.</small></div>`}
      </div>
      ${gateWarnings.length ? `<small class="small-account-gate-warning">주의: ${gateWarnings.slice(0, 2).map((item) => escapeHtml(item)).join(" · ")}</small>` : ""}
    `;
  }
  const reportNode = el("#smallAccountReportSchedule");
  if (reportNode) {
    const nextReport = reportSchedule.next_slot || {};
    const dispatchState = reportSchedule.dispatch_state || {};
    const reportSlots = Array.isArray(reportSchedule.slots) ? reportSchedule.slots : [];
    const todayRuns = Array.isArray(reportSchedule.today_runs) ? reportSchedule.today_runs : [];
    const todaySlots = Array.isArray(reportSchedule.today_slots) ? reportSchedule.today_slots : [];
    const todaySlotSummary = reportSchedule.today_slot_summary || {};
    const nextPreview = reportSchedule.next_preview || {};
    const nextPreviewItems = Array.isArray(nextPreview.items) ? nextPreview.items : [];
    const silentItems = Array.isArray(reportSchedule.silent_items) ? reportSchedule.silent_items : [];
    const allowedReports = Array.isArray(reportSchedule.allowed_reports) ? reportSchedule.allowed_reports : [];
    const nextReportAt = nextReport.next_at || "";
    reportNode.innerHTML = `
      <div class="small-account-report-head">
        <div>
          <strong>텔레그램 보고 시간표</strong>
          <span>${escapeHtml(reportSchedule.mode || "시간표 확인")}${reportSchedule.quiet_learning ? " · 연구는 조용히 기록" : " · 연구 자동보고 켜짐"}</span>
        </div>
        <b class="${reportSchedule.enabled ? "ready" : "blocked"}">${escapeHtml(nextReport.label || "보고 꺼짐")}</b>
      </div>
      <div class="small-account-report-next">
        <b>다음 보고</b>
        <span>${escapeHtml(nextReport.status || "대기")}</span>
        <span>${escapeHtml(nextReportAt ? formatDateTimeShort(nextReportAt) : "-")}</span>
        <span data-countdown-at="${escapeHtml(nextReportAt)}" data-countdown-minutes="${escapeHtml(String(nextReport.minutes_to_next ?? ""))}">${escapeHtml(formatEventCountdown(nextReportAt, nextReport.minutes_to_next))}</span>
      </div>
      <div class="small-account-report-dispatch">
        <span>보고대기 ${Number(dispatchState.pending_total || 0)}건</span>
        <span>최근 ${Number(dispatchState.pending_recent || 0)}건</span>
        <span>자동발송 ${dispatchState.auto_dispatch ? "켜짐" : "꺼짐"}</span>
        <span>발송기 ${dispatchState.dispatcher_running ? "동작" : "대기"}</span>
        <span>스팸방지 ${dispatchState.dedupe_enabled || dispatchState.rate_limit_enabled ? "켜짐" : "꺼짐"}</span>
      </div>
      <div class="small-account-report-history">
        <strong>오늘 보고 이력 ${Number(reportSchedule.today_run_count || 0)}건</strong>
        ${todayRuns.length
          ? todayRuns.slice(0, 3).map((run) => `
            <span>${escapeHtml(run.label || run.slot_id || "-")} · ${escapeHtml(run.created_at ? formatDateTimeShort(run.created_at) : "-")} · ${run.queued ? "큐 등록" : "스킵"}</span>
          `).join("")
          : `<span>오늘 자동 보고 없음</span>`}
      </div>
      <div class="small-account-report-today">
        <strong>오늘 시간표 완료 ${Number(todaySlotSummary.done || 0)}/${Number(todaySlotSummary.total || 0)}</strong>
        ${todaySlots.length
          ? todaySlots.slice(0, 6).map((slot) => {
            const statusClass = slot.status === "완료" ? "done" : slot.status === "예정" || slot.status === "보고 가능" ? "pending" : slot.status === "지나감" ? "missed" : "off";
            return `<span class="${statusClass}">${escapeHtml(slot.label || slot.id || "-")} · ${escapeHtml(slot.status || "-")}</span>`;
          }).join("")
          : `<span class="off">오늘 시간표 대기</span>`}
      </div>
      ${nextPreviewItems.length ? `
        <div class="small-account-report-preview">
          <strong>${escapeHtml(nextPreview.title || "다음 보고 미리보기")}</strong>
          ${nextPreviewItems.slice(0, 4).map((item, index) => `
            <div><b>${index + 1}</b><span>${escapeHtml(item)}</span></div>
          `).join("")}
        </div>
      ` : ""}
      <div class="small-account-report-slots">
        ${reportSlots.length
          ? reportSlots.slice(0, 6).map((slot) => `
            <span class="${slot.enabled ? "on" : "off"}">${escapeHtml(slot.label || slot.id || "-")} · ${escapeHtml(slot.time || "-")}</span>
          `).join("")
          : `<span class="off">보고 시간표 대기</span>`}
      </div>
      <small>허용: ${allowedReports.slice(0, 4).map((item) => escapeHtml(item)).join(" · ") || "시간표 보고"} / 조용히 기록: ${silentItems.slice(0, 3).map((item) => escapeHtml(item)).join(" · ") || "연구 로그"}</small>
    `;
  }
  const workerNode = el("#smallAccountWorkers");
  if (workerNode) {
    workerNode.innerHTML = workerFocus.length
      ? workerFocus.map((worker) => {
        const priority = String(worker.priority || "-");
        const priorityClass = priority === "높음" ? "urgent" : priority === "계속" ? "steady" : "normal";
        const nextAt = worker.next_event_at ? formatDateTimeShort(worker.next_event_at) : "시간 대기";
        const remaining = formatEventCountdown(worker.next_event_at, worker.minutes_to_next);
        const gateSummary = worker.gate_state
          ? ` · 게이트 ${worker.gate_state} · 차단 ${Number(worker.gate_blocker_count || 0)}개`
          : "";
        return `
          <div class="small-account-worker ${priorityClass}">
            <div>
              <strong>${escapeHtml(worker.owner || "AI 직원")}</strong>
              <span>${escapeHtml(worker.status || "대기")} · ${escapeHtml(worker.target || "-")}</span>
            </div>
            <div class="small-account-worker-availability ${worker.executable_now ? "ready" : "waiting"}">
              <b>${escapeHtml(worker.availability || "상태 확인")}</b>
              <span>${escapeHtml(worker.availability_reason || "실행 가능 상태를 확인 중입니다.")}</span>
            </div>
            <p>${escapeHtml(worker.action || "배정된 작업을 기다립니다.")}</p>
            <div class="small-account-worker-next">
              <b>${escapeHtml(worker.next_event || "다음 확인")}</b>
              <span>${escapeHtml(nextAt)}</span>
              <span data-countdown-at="${escapeHtml(worker.next_event_at || "")}" data-countdown-minutes="${escapeHtml(String(worker.minutes_to_next ?? ""))}">${escapeHtml(remaining)}</span>
            </div>
            <small>작업 ${Number(worker.task_count || 0)}개 · 높음 ${Number(worker.high_priority_count || 0)}개 · 계속 ${Number(worker.continuous_count || 0)}개${escapeHtml(gateSummary)}</small>
          </div>
        `;
      }).join("")
      : `<div class="small-account-worker empty"><strong>AI 직원 배정 대기</strong><p>작업 큐가 갱신되면 매매 직원과 연구 직원 업무가 나뉘어 표시됩니다.</p></div>`;
  }
  const holdingNode = el("#smallAccountHoldings");
  if (holdingNode) {
    holdingNode.innerHTML = holdings.length
      ? holdings.map((row) => `
        <div class="small-account-row">
          <strong>${escapeHtml(row.name || row.symbol || "-")}</strong>
          <span class="${Number(row.pnl_pct || 0) >= 0 ? "up" : "down"}">${pct(row.pnl_pct || 0)}</span>
          <small>${escapeHtml(row.decision || "-")} · ${escapeHtml(row.reason || "-")}</small>
          <small>현재 ${formatKrw(row.current_price || 0)} · 손절 ${formatKrw(row.stop_price || 0)} · 수익보호 ${formatKrw(row.take_profit_price || 0)} · ${escapeHtml(row.trade_mode || "-")}</small>
        </div>
      `).join("")
      : `<div class="small-account-row empty"><strong>보유 종목 없음</strong><small>현금 기준으로 다음 후보를 기다립니다.</small></div>`;
  }
  const candidateNode = el("#smallAccountCandidates");
  if (candidateNode) {
    candidateNode.innerHTML = candidates.length
      ? candidates.slice(0, 4).map((row, index) => `
        <div class="small-account-row candidate">
          <strong>${index + 1}. ${escapeHtml(row.name || row.symbol || "-")}</strong>
          <span>${Number(row.growth_score || 0).toFixed(1)}점</span>
          <small>1주 ${formatKrw(row.estimated_notional || 0)} · ${escapeHtml(row.trade_mode || "-")} · 손절 ${Number(row.stop_loss_pct || 0).toFixed(1)}% · 익절 ${Number(row.take_profit_pct || 0).toFixed(1)}%</small>
        </div>
      `).join("")
      : watchCandidates.length
        ? watchCandidates.slice(0, 4).map((row, index) => `
          <div class="small-account-row">
            <strong>감시 ${index + 1}. ${escapeHtml(row.name || row.symbol || "-")}</strong>
            <span>${Number(row.score || 0).toFixed(1)}점</span>
            <small>1주 ${formatKrw(row.estimated_notional || 0)} · ${escapeHtml((row.block_reasons || []).slice(0, 2).join(" · ") || "재검증 대기")}</small>
          </div>
        `).join("")
        : `<div class="small-account-row empty"><strong>신규 후보 대기</strong><small>현재 현금/가격/품질 조건을 동시에 통과한 후보가 없습니다.</small></div>`;
  }
  const learningNode = el("#smallAccountLearning");
  if (learningNode) {
    const cards = Array.isArray(learning.cards) ? learning.cards : [];
    const studyRules = Array.isArray(daytradeStudy.rules) ? daytradeStudy.rules : [];
    const studyScore = Number(daytradeStudy.score || 0);
    const exitChecklist = Array.isArray(positionExitPlan.checklist) ? positionExitPlan.checklist : [];
    const exitTop = positionExitPlan.top_candidate || {};
    const exitTopName = exitTop.name || exitTop.symbol || "";
    learningNode.innerHTML = `
      <strong>학습 점수 ${Number(learning.score || 0).toFixed(0)} · 하루 ${limits.max_daily_orders || 0}회 이하 · ${escapeHtml(limits.quantity_rule || "1주 단위")}</strong>
      <span>현재 임무: ${escapeHtml(currentTask.title || "대기")} · ${escapeHtml(currentTask.target || "-")} · ${escapeHtml(currentTask.next_event || "-")}</span>
      <span>${cards.slice(0, 2).map((card) => escapeHtml(card.title || card.lesson || "-")).join(" · ") || "학습 인사이트 대기"}</span>
      <span>${studyScore ? `단타 공부 ${studyScore.toFixed(0)}점 · ${studyRules.slice(0, 4).map((rule) => escapeHtml(rule)).join(" · ")}` : "단타 공부 자료 수집 대기"}</span>
      <span>소액 단타 스카우트 ${scoutItems.length}개 · 2차 통과 ${Number(daytradeScoutValidation.validated_count || 0)}개 · 감시 ${Number(daytradeScoutValidation.watch_count || 0)}개</span>
      <span>매도 재확인 ${Number(positionExitPlan.sell_candidate_count || 0)}개${exitTopName ? ` · ${escapeHtml(exitTopName)}` : ""} · ${escapeHtml(positionExitPlan.phase_label || "-")} · ${escapeHtml(positionExitPlan.next_event || "-")}</span>
      <span>${escapeHtml(positionExitPlan.summary || exitChecklist.slice(0, 2).join(" · ") || "보유 종목 재확인 대기")}</span>
    `;
  }
  const actionNode = el("#smallAccountActions");
  if (actionNode) {
    const actionPhase = currentTask.phase_label || positionExitPlan.phase_label || "-";
    const actionNextEvent = currentTask.next_event || positionExitPlan.next_event || "-";
    const actionNextAt = currentTask.next_event_at || positionExitPlan.next_event_at || "";
    const actionNextTime = actionNextAt ? formatDateTimeShort(actionNextAt) : "시간 대기";
    const actionRemaining = formatEventCountdown(actionNextAt, positionExitPlan.minutes_to_next);
    actionNode.innerHTML = `
      <div class="small-account-actions-head">
        <strong>AI 다음 행동</strong>
        <span>${escapeHtml(actionPhase)} · ${escapeHtml(actionNextEvent)} · ${escapeHtml(actionNextTime)} · <em data-countdown-at="${escapeHtml(actionNextAt || "")}" data-countdown-minutes="${escapeHtml(String(positionExitPlan.minutes_to_next ?? ""))}">${escapeHtml(actionRemaining)}</em></span>
      </div>
      <div class="small-account-action-list">
        ${nextActionItems.length
          ? nextActionItems.slice(0, 6).map((item, index) => {
            const priority = String(item.priority || "보통");
            const priorityClass = priority === "높음" ? "urgent" : priority === "계속" ? "steady" : "normal";
            return `
            <div class="small-account-action ${priorityClass}">
              <b>${index + 1}</b>
              <div class="small-account-action-body">
                <strong>
                  <i>${escapeHtml(item.owner || "AI 직원")}</i>
                  <em>${escapeHtml(priority)}</em>
                  <small>${escapeHtml(item.status || "대기")}</small>
                </strong>
                <span>${escapeHtml(item.action || "-")}</span>
                <small>대상 ${escapeHtml(item.target || "-")} · ${escapeHtml(item.reason || item.kind || "작업 이유 기록 대기")}</small>
              </div>
            </div>
          `;
          }).join("")
          : `<div class="small-account-action empty"><b>1</b><span>AI 작업 큐를 불러오는 중입니다.</span></div>`}
      </div>
    `;
  }
  updateSmallAccountCountdowns();
}

async function refreshSmallAccountGrowth(force = true) {
  const button = el("#smallAccountRefresh");
  if (button) {
    button.disabled = true;
    button.textContent = "재확인 중";
  }
  setSmallAccountRefreshStatus("running", "계좌·후보·보유 판단 재계산 중", 180000);
  try {
    const response = await fetch(`/api/agent/small-account-growth?force=${force ? "1" : "0"}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "소액계좌 플랜 재확인 실패");
    renderSmallAccountGrowth(result);
    setSmallAccountRefreshStatus("done", `완료 · ${result.current_ai_task?.target || "작업 갱신"}`, 120000);
    addLog(`소액계좌 플랜 재확인 완료: ${result.current_ai_task?.title || "작업 갱신"}`);
    return result;
  } catch (error) {
    setSmallAccountRefreshStatus("error", `실패 · ${error.message}`, 180000);
    addLog(`소액계좌 플랜 재확인 실패: ${error.message}`);
    throw error;
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "지금 재확인";
    }
  }
}

async function loadAiStaff() {
  try {
    const response = await fetch("/api/agent/staff/quick?ttl=60");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "AI 직원 상태 조회 실패");
    const board = result.worker_board || result || {};
    const workers = Array.isArray(board.workers) ? board.workers : [];
    const counts = board.counts || {};
    const summary = board.summary || {};
    const operator = workers.find((row) => row.id === "operator") || {};
    setText("aiStaffState", `직원 상태판 · 활성 ${Number(summary.active || 0)}명 · 작업 ${Number(summary.working || 0)}명 · 감시 ${Number(summary.monitoring || 0)}명 · 주의 ${Number(summary.attention || 0)}명`);
    setText("aiStaffBrief", operator.task ? `매매직원 ${operator.status_label || operator.state || "대기"}: ${operator.task} · ${operator.target || "-"} · 승인대기 ${counts.pending_approvals || 0}건` : result.safety || "운용 AI와 연구 AI가 역할을 나눠 일합니다.");
    renderAiStaffRows("#aiStaffRoles", workers, "AI 직원 상태 대기");
    renderAiStaffRows("#aiStaffMeetingRows", workers.slice(0, 2), "직원 작업 로그 대기");
    await loadAiStaffMeetingSplit();
  } catch (error) {
    setText("aiStaffState", "조회 실패");
    renderAiStaffMeetingSplit({}, {});
    renderSmallAccountGrowth({ ok: false });
    renderOhlcvChallengeCard({ ok: false, message: "AI 직원 상태 조회 실패로 연구 결과를 표시하지 못했습니다." });
  }
}

function renderOpsList(selector, rows = [], emptyText = "기록 없음") {
  const node = el(selector);
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 10).map((row) => {
      const status = row.status || row.action || "-";
      const symbol = row.symbol || row.ticket?.symbol || row.payload?.ticket?.symbol || "";
      const side = row.side || row.ticket?.side || row.payload?.ticket?.side || "";
      const title = symbol ? `${symbolDisplayName(symbol, row)} ${side}` : row.message || row.id || row.token || "-";
      const detail = row.created_at || row.expires_at || row.action || "";
      const klass = String(status).includes("BLOCK") || String(status).includes("rejected") ? "down" : String(status).includes("PASS") || String(status).includes("approved") || String(status).includes("FILLED") ? "up" : "flat";
      return `<div class="ops-item">
        <strong>${title}</strong>
        <span class="${klass}">${escapeHtml(koreanStatusText(status))}</span>
        <small>${detail}</small>
      </div>`;
    }).join("")
    : `<div class="ops-item"><strong>${emptyText}</strong><small>운영 이벤트가 생기면 여기에 쌓입니다.</small></div>`;
}

function renderOpsPlaybook(playbook = {}) {
  const featureNode = el("#opsAbsorptionRows");
  const actionNode = el("#opsNextActions");
  const features = Array.isArray(playbook.absorbed_features) ? playbook.absorbed_features : [];
  const actions = Array.isArray(playbook.next_actions) ? playbook.next_actions : [];
  if (featureNode) {
    featureNode.innerHTML = features.length
      ? features.map((item) => {
        const status = item.status || "ACTIVE";
        const klass = status === "ACTIVE" ? "up" : status === "READONLY" ? "flat" : "down";
        return `
          <div class="ops-feature">
            <strong>${productHtml(item.name || "-")}</strong>
            <span class="${klass}">${productHtml(status)}</span>
            <small>${productHtml(item.impact || item.source || "-")}</small>
          </div>
        `;
      }).join("")
      : `<div class="ops-feature"><strong>안전 기능 대기</strong><small>운영 상태를 불러오면 표시됩니다.</small></div>`;
  }
  if (actionNode) {
    actionNode.innerHTML = actions.length
      ? actions.map((item, index) => `<div class="ops-next"><b>${index + 1}</b><span>${productHtml(replaceSymbolCodesInText(item))}</span></div>`).join("")
      : `<div class="ops-next"><b>1</b><span>AI 작업 큐를 불러오는 중입니다.</span></div>`;
  }
}

function kisFeatureStatusClass(status = "") {
  const text = String(status);
  if (["완료", "ACTIVE", "ORDER_READY"].includes(text)) return "up";
  if (["부분완료", "읽기잠금", "키필요", "READONLY", "다음"].includes(text)) return "flat";
  return "down";
}

function renderKisFeatureAbsorption(plan = {}) {
  const featureNode = el("#kisFeatureAbsorptionRows");
  const actionNode = el("#kisFeatureNextRows");
  const features = Array.isArray(plan.features) ? plan.features : [];
  const actions = Array.isArray(plan.next_actions) ? plan.next_actions : [];
  if (featureNode) {
    featureNode.innerHTML = features.length
      ? features.map((item) => {
        const status = item.status || "-";
        const klass = kisFeatureStatusClass(status);
        return `
          <div class="ops-feature kis-feature-card">
            <strong>${Number(item.phase || 0).toString().padStart(2, "0")}. ${escapeHtml(item.name || "-")}</strong>
            <span class="${klass}">${escapeHtml(status)}</span>
            <small>${escapeHtml(item.impact || "-")}</small>
            <em>${escapeHtml(item.current || "-")}</em>
            <b>${escapeHtml(item.next_step || "-")}</b>
          </div>
        `;
      }).join("")
      : `<div class="ops-feature"><strong>한투 기능 구현 순서 대기</strong><small>운영 상태를 불러오면 표시됩니다.</small></div>`;
  }
  if (actionNode) {
    const summary = plan.summary || {};
    const header = plan.headline
      ? `<div class="ops-next kis-feature-summary"><b>${Number(summary.done || 0)}</b><span>${escapeHtml(plan.headline)} · 전체 ${Number(summary.total || 0)}개 중 완료 ${Number(summary.done || 0)}개, 보강 ${Number(summary.partial || 0)}개</span></div>`
      : "";
    actionNode.innerHTML = `${header}${actions.length
      ? actions.map((item, index) => `<div class="ops-next"><b>${index + 1}</b><span>${escapeHtml(item)}</span></div>`).join("")
      : `<div class="ops-next"><b>1</b><span>다음 구현 순서를 계산하는 중입니다.</span></div>`}`;
  }
}

function renderRuntimeStorageCard(storage = {}, separation = {}, hotLogs = {}) {
  const node = el("#runtimeStorageCard");
  if (!node) return;
  const transition = storage.transition_state || "unknown";
  const tone = transition === "sqlite_active_partial_backfill" || transition === "indexed"
    ? "up"
    : transition === "jsonl_only" ? "down" : "flat";
  const opsStorageActive = separation.ops_storage_active || "repo_data";
  const opsStorageTone = opsStorageActive === "user_data_dir" ? "up" : "flat";
  const opsStorageLabel = opsStorageActive === "user_data_dir" ? "분리됨" : "코드폴더";
  const runtimeStorageActive = separation.runtime_storage_active || "repo_data";
  const runtimeStorageTone = runtimeStorageActive === "user_data_dir" ? "up" : "flat";
  const runtimeStorageLabel = runtimeStorageActive === "user_data_dir" ? "분리됨" : "코드폴더";
  const sources = Array.isArray(storage.sources) ? storage.sources : [];
  const topSources = sources
    .filter((item) => Number(item.indexed_count || 0) || item.exists)
    .slice(0, 5);
  const hotFiles = Array.isArray(hotLogs.top_files) ? hotLogs.top_files.slice(0, 3) : [];
  const hotTone = hotLogs.tone === "danger" ? "down" : hotLogs.tone === "warn" ? "flat" : hotLogs.tone === "watch" ? "flat" : "up";
  const residual = separation.repo_residual_summary || {};
  const cleanup = separation.repo_residual_cleanup_plan || {};
  const readiness = cleanup.cleanup_readiness || separation.cleanup_readiness || {};
  const readinessScore = Number(readiness.score || 0);
  const readinessTone = readiness.status === "clear" || readiness.status === "archive_ready"
    ? "up"
    : readiness.status === "copy_required" || readiness.status === "manual_review" || readiness.status === "verify_required"
      ? "flat"
      : "wait";
  const archivePreview = Array.isArray(cleanup.safe_archive_preview) ? cleanup.safe_archive_preview.slice(0, 3) : [];
  const copyPreview = Array.isArray(cleanup.copy_required_preview) ? cleanup.copy_required_preview.slice(0, 2) : [];
  const verifyPreview = Array.isArray(cleanup.verify_required_preview) ? cleanup.verify_required_preview.slice(0, 2) : [];
  const cleanupRows = [
    ...archivePreview.map((item) => ({ ...item, tone: "up", label: "보관 후보" })),
    ...copyPreview.map((item) => ({ ...item, tone: "flat", label: "복사 필요" })),
    ...verifyPreview.map((item) => ({ ...item, tone: "flat", label: "재검증" })),
  ].slice(0, 5);
  const coverage = Number(storage.coverage_pct || 0);
  node.className = `ops-storage-card ${tone}`;
  node.innerHTML = `
    <div class="ops-storage-head">
      <div>
        <strong>런타임 저장소</strong>
        <span>${escapeHtml(transition === "sqlite_active_partial_backfill" ? "JSONL 원본 + SQLite 빠른 인덱스 작동 중" : storage.mode || "저장소 상태 대기")}</span>
      </div>
      <button id="runtimeStorageBackfill" type="button">SQLite 소규모 백필</button>
    </div>
    <div class="ops-storage-grid">
      <div><b>${Number(storage.total_indexed_events || 0).toLocaleString()}</b><small>SQLite 이벤트</small></div>
      <div><b>${Number(storage.indexed_sources || 0).toLocaleString()} / ${Number(storage.existing_jsonl_sources || 0).toLocaleString()}</b><small>색인 소스</small></div>
      <div><b class="${tone}">${coverage.toFixed(1)}%</b><small>소스 커버리지</small></div>
      <div><b>${storage.db_exists ? "ON" : "OFF"}</b><small>SQLite DB</small></div>
      <div><b class="${opsStorageTone}">${escapeHtml(opsStorageLabel)}</b><small>OPS 개인데이터</small></div>
      <div><b class="${runtimeStorageTone}">${escapeHtml(runtimeStorageLabel)}</b><small>JSONL/SQLite</small></div>
      <div><b class="${hotTone}">${Number(hotLogs.total_size_mb || 0).toFixed(1)}MB</b><small>핫 로그</small></div>
      <div><b class="${hotTone}">${Number(hotLogs.warn_count || 0) + Number(hotLogs.danger_count || 0)}</b><small>경고/위험</small></div>
      <div><b class="${readinessTone}">${readinessScore.toFixed(1)}%</b><small>정리 준비도</small></div>
      <div><b class="${Number(residual.target_missing || 0) ? "flat" : "up"}">${Number(residual.target_exists || 0).toLocaleString()} / ${Number(residual.total || 0).toLocaleString()}</b><small>잔여 복사확인</small></div>
      <div><b class="${Number(residual.safe_archive_candidates || 0) ? "flat" : "up"}">${Number(residual.safe_archive_candidates || 0).toLocaleString()}</b><small>정리 후보</small></div>
      <div><b class="${Number(cleanup.copy_required_count || 0) ? "flat" : "up"}">${Number(cleanup.copy_required_count || 0).toLocaleString()}</b><small>복사 필요</small></div>
      <div><b class="${Number(cleanup.verify_required_count || 0) ? "flat" : "up"}">${Number(cleanup.verify_required_count || 0).toLocaleString()}</b><small>재검증</small></div>
    </div>
    <div class="ops-storage-source-list">
      ${topSources.length ? topSources.map((item) => `
        <span>
          <b>${escapeHtml(item.source_name || "-")}</b>
          <small>${Number(item.indexed_count || 0).toLocaleString()}건 · ${escapeHtml(item.read_mode || "-")}</small>
        </span>
      `).join("") : `<span><b>색인 대기</b><small>백필을 실행하면 최근 JSONL 기록이 SQLite에 복사됩니다.</small></span>`}
    </div>
    <div class="ops-storage-source-list">
      ${hotFiles.length ? hotFiles.map((item) => `
        <span>
          <b>${escapeHtml(item.name || "-")}</b>
          <small>${Number(item.size_mb || 0).toFixed(2)}MB · ${escapeHtml(item.tone || "-")}</small>
        </span>
      `).join("") : `<span><b>핫 로그 정상</b><small>크게 커진 JSONL/SQLite 로그가 없습니다.</small></span>`}
    </div>
    <div class="ops-storage-cleanup-list">
      ${cleanupRows.length ? cleanupRows.map((item) => `
        <span class="${escapeHtml(item.tone || "flat")}">
          <b>${escapeHtml(item.label || "정리")}</b>
          <small>${escapeHtml(item.path || "-")}</small>
          <em>${escapeHtml(item.mirror_status || item.action || "-")}</em>
        </span>
      `).join("") : `<span class="up"><b>정리 후보 없음</b><small>repo 잔여 파일 dry-run 계획이 없습니다.</small><em>파일 이동/삭제 없음</em></span>`}
    </div>
    <small>${escapeHtml(hotLogs.headline || "핫 로그 용량 진단 대기")}</small>
    <small>잔여 정리 상태: ${escapeHtml(readiness.label || "진단 대기")} · ${escapeHtml(readiness.next_action || "dry-run 결과를 기다리는 중입니다.")}</small>
    <small>${escapeHtml(cleanup.headline || "개인 데이터 잔여 정리 dry-run 대기")}</small>
    <small>${escapeHtml(storage.coverage_basis || storage.next || "원본 JSONL은 유지하고 SQLite는 빠른 조회 보조 레이어로 사용합니다.")}</small>
    <small>OPS 저장 경로: ${escapeHtml(separation.ops_data_dir || "-")}</small>
    <small>런타임 저장 루트: ${escapeHtml(separation.runtime_data_root || "-")}</small>
  `;
}

function featureHealthTone(status) {
  if (status === "fail") return "down";
  if (status === "watch") return "flat";
  if (status === "ok") return "up";
  return "wait";
}

function renderFeatureHealthCard(health = {}) {
  const node = el("#featureHealthCard");
  if (!node) return;
  const rowsNode = el("#featureHealthRows");
  const overall = health.overall || "wait";
  const tone = featureHealthTone(overall);
  const checks = Array.isArray(health.checks) ? health.checks : [];
  const issueRows = [
    ...(Array.isArray(health.failing_buttons) ? health.failing_buttons : []),
    ...(Array.isArray(health.attention_buttons) ? health.attention_buttons : (Array.isArray(health.watch_buttons) ? health.watch_buttons : [])),
    ...(Array.isArray(health.warning_buttons) ? health.warning_buttons : []),
  ];
  const rows = (issueRows.length ? issueRows : checks).slice(0, 6);
  const normalCount = Number(health.normal_count ?? health.alive_count ?? health.ok_count ?? 0);
  const delayedCount = Number(health.delayed_count ?? 0);
  const verificationPendingCount = Number(
    health.verification_pending_count ?? health.visible_warning_count ?? health.attention_count ?? health.watch_count ?? 0,
  );
  const brokenCount = Number(health.operational_broken_count ?? health.broken_count ?? health.fail_count ?? 0);
  const surfaceCoverage = health.surface_coverage || {};
  const engineHealth = health.external_engine_health || {};
  node.className = `feature-health-card ${tone}`;
  node.querySelector(".feature-health-grid").innerHTML = `
    <div><b class="up">${normalCount.toLocaleString()}</b><small>정상</small></div>
    <div><b class="flat">${delayedCount.toLocaleString()}</b><small>지연</small></div>
    <div><b class="flat">${verificationPendingCount.toLocaleString()}</b><small>검증대기</small></div>
    <div><b class="down">${brokenCount.toLocaleString()}</b><small>고장</small></div>
    <div><b class="${tone}">${Number(health.score || 0).toFixed(1)}</b><small>점수</small></div>
  `;
  const head = node.querySelector(".feature-health-head span");
  if (head) {
    const total = Number(health.total || checks.length || 0);
    const cached = health.cached ? ` · 캐시 ${Number(health.cache_age_seconds || 0).toFixed(0)}초` : "";
    const buttonCoverage = surfaceCoverage.ui_buttons || {};
    const apiCoverage = surfaceCoverage.ui_api_calls || {};
    const mcpCoverage = surfaceCoverage.mcp_tools || {};
    const coverageBits = [];
    if (Number(buttonCoverage.total_count || 0)) {
      coverageBits.push(`버튼 ${Number(buttonCoverage.covered_count || 0)}/${Number(buttonCoverage.total_count || 0)}`);
    }
    if (Number(apiCoverage.total_count || 0)) {
      coverageBits.push(`API ${Number(apiCoverage.covered_count || 0)}/${Number(apiCoverage.total_count || 0)}`);
    }
    if (Number(mcpCoverage.total_count || 0)) {
      coverageBits.push(`MCP ${Number(mcpCoverage.covered_count || 0)}/${Number(mcpCoverage.total_count || 0)}`);
    }
    if (Number(engineHealth.engine_count || 0)) {
      coverageBits.push(`엔진 감시 ${Number(engineHealth.monitored_count || 0)}/${Number(engineHealth.engine_count || 0)}`);
    }
    const coverage = coverageBits.length ? ` · ${coverageBits.join(" · ")}` : "";
    head.textContent = total
      ? `전체 ${total}개 · 정상 ${normalCount} · 지연 ${delayedCount} · 검증대기 ${verificationPendingCount} · 고장 ${brokenCount}${coverage}${cached}`
      : "버튼/API가 실제로 살아있는지 읽기전용으로 확인합니다.";
  }
  if (rowsNode) {
    rowsNode.innerHTML = rows.length
      ? rows.map((row) => {
        const operationalState = row.operational_state || (row.status === "fail" ? "broken" : row.status === "ok" ? "normal" : "verification_pending");
        const rowTone = operationalState === "broken" ? "down" : operationalState === "normal" ? "up" : "flat";
        const action = row.next_action || row.detail || "점검 완료";
        const button = row.button_id ? ` · 버튼 ${row.button_id}` : "";
        const state = row.operational_state_label || row.state_label || String(row.status || "-").toUpperCase();
        const replayWorker = row.regeneration_worker || {};
        const replayEstimate = row.regeneration_estimate || {};
        const replayWorkerHealth = replayWorker.health_label || replayWorker.health_state || "";
        const replayEta = Number.isFinite(Number(replayEstimate.estimated_hours_remaining))
          ? ` · ETA ${Number(replayEstimate.estimated_hours_remaining).toFixed(1)}h`
          : "";
        const replayDuty = Number.isFinite(Number(replayEstimate.estimated_worker_duty_cycle_pct))
          ? ` · duty ${Number(replayEstimate.estimated_worker_duty_cycle_pct).toFixed(1)}%`
          : "";
        const recovery = row.regeneration_progress?.label
          ? ` | Replay recovery ${row.regeneration_progress.label}${replayWorkerHealth ? ` · ${replayWorkerHealth}` : ""}${replayEta}${replayDuty}`
          : (replayWorkerHealth ? ` | Replay worker ${replayWorkerHealth}` : "");
        const lastSuccess = row.last_success_at ? formatDateTimeShort(row.last_success_at) : "성공 기록 없음";
        const successEvidence = row.success_evidence_label || (row.last_success_at ? "성공 증거 있음" : "성공 기록 없음");
        const latency = Number.isFinite(Number(row.latency_ms)) ? ` · ${Number(row.latency_ms).toLocaleString()}ms` : "";
        return `<span class="${rowTone}">
          <b>${escapeHtml(row.label || row.id || "기능")}</b>
          <small>${escapeHtml(state)}${button} · ${escapeHtml(row.endpoint || "-")}${escapeHtml(recovery)}${escapeHtml(latency)}</small>
          <small>마지막 성공 ${escapeHtml(lastSuccess)} · ${escapeHtml(successEvidence)}</small>
          <em>${escapeHtml(action)}</em>
        </span>`;
      }).join("")
      : `<span class="up"><b>전체 정상</b><small>감지된 실패/주의 기능이 없습니다.</small><em>${escapeHtml(health.safety || "읽기전용 자동감지")}</em></span>`;
  }
}

async function refreshFeatureHealth(force = true) {
  const button = el("#featureHealthRefresh");
  if (button) button.disabled = true;
  try {
    const response = await fetch(`/api/system/feature-health?compact=1${force ? "&force=1" : ""}`);
    const health = await response.json();
    if (!response.ok || health.ok === false && health.fail_count === undefined) {
      throw new Error(health.error || "기능 자동감지 실패");
    }
    renderFeatureHealthCard(health);
    addLog(`기능 자동감지: 고장 ${Number(health.broken_count ?? health.fail_count ?? 0)}개, 정리필요 ${Number(health.attention_count ?? health.watch_count ?? 0)}개`);
    return health;
  } catch (error) {
    const node = el("#featureHealthRows");
    if (node) node.innerHTML = `<span class="down"><b>자동감지 실패</b><small>${escapeHtml(error.message || "-")}</small></span>`;
    addLog(`기능 자동감지 실패: ${error.message}`);
    return null;
  } finally {
    if (button) button.disabled = false;
  }
}

async function loadHotLogStorage(silent = true) {
  if (state.hotLogStorageLoading) return state.hotLogStorage;
  state.hotLogStorageLoading = true;
  try {
    const response = await fetch("/api/ops/storage/hot-logs?limit=8&ttl=60");
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "핫 로그 진단 실패");
    state.hotLogStorage = result;
    state.hotLogStorageLoadedAt = Date.now();
    const status = state.lastOpsStatus || {};
    renderRuntimeStorageCard(status.runtime_storage || {}, status.data_separation || {}, result);
    if (!silent) addLog(`핫 로그 진단: ${result.headline || "-"}`);
    return result;
  } catch (error) {
    if (!silent) addLog(`핫 로그 진단 실패: ${error.message}`);
    return null;
  } finally {
    state.hotLogStorageLoading = false;
  }
}

function renderExternalKnowledge(report = {}) {
  setText("externalKnowledgeStage", report.stage || "외부 지식 수입/검증 준비 중");
  setText("externalSourceCount", Number(report.source_count || 0).toLocaleString());
  setText("externalPackageCount", Number(report.package_count || 0).toLocaleString());
  setText("externalValidationScore", `${Number(report.avg_validation_score || 0).toFixed(1)}점`);
  setText("externalWarningCount", `${Number(report.warning_count || 0).toLocaleString()} / ${Number(report.block_count || 0).toLocaleString()}`);
  setText("externalKnowledgeSafety", report.safety || "외부 코드는 실행하지 않습니다. 실전 주문, 계좌 설정, API 키 접근은 차단됩니다.");
  const sourcesNode = el("#externalKnowledgeSources");
  const sources = Array.isArray(report.sources) ? report.sources : [];
  if (sourcesNode) {
    sourcesNode.innerHTML = sources.length
      ? sources.slice(0, 6).map((source) => {
          const absorb = Array.isArray(source.what_to_absorb) ? source.what_to_absorb.slice(0, 2).join(" · ") : "";
          return `<span>
            <b>${escapeHtml(source.source_name || "-")}</b>
            <small>${escapeHtml(absorb || source.safe_use || "학습 후보")}</small>
          </span>`;
        }).join("")
      : `<span><b>소스 카탈로그 대기</b><small>외부 소스 목록을 불러오는 중입니다.</small></span>`;
  }
  const packagesNode = el("#externalKnowledgePackages");
  const packages = Array.isArray(report.recent_packages) ? report.recent_packages : [];
  if (packagesNode) {
    packagesNode.innerHTML = packages.length
      ? packages.slice(0, 5).map((pkg) => {
          const validation = pkg.validation && typeof pkg.validation === "object" ? pkg.validation : {};
          const blockCount = Array.isArray(validation.blocks) ? validation.blocks.length : 0;
          const warningCount = Array.isArray(validation.warnings) ? validation.warnings.length : 0;
          const tone = blockCount ? "blocked" : warningCount ? "warn" : "ok";
          return `<article class="${tone}">
            <strong>${escapeHtml(pkg.strategy_name || pkg.package_id || "외부 전략")}</strong>
            <span>${escapeHtml(pkg.source_name || "-")} · ${escapeHtml(pkg.status || "VALIDATING")} · 검증 ${Number(validation.score || 0).toFixed(1)}점</span>
            <small>${escapeHtml(validation.summary || pkg.description || "검증 결과 대기")}</small>
          </article>`;
        }).join("")
      : `<article class="warn">
          <strong>아직 수입된 외부 전략 없음</strong>
          <span>ChatGPT/MCP 또는 JSON 수입 API로 전략 패키지를 넣으면 여기에 검증 결과가 쌓입니다.</span>
          <small>우선 Lean, NautilusTrader, vectorbt, Freqtrade 같은 구조를 안전하게 분석 대상으로 삼습니다.</small>
        </article>`;
  }
}

async function loadExternalKnowledge(silent = true) {
  try {
    const response = await fetch("/api/external-knowledge/report?limit=8");
    const report = await response.json();
    if (!response.ok || report.ok === false) throw new Error(report.error || "외부학습 보고서 조회 실패");
    renderExternalKnowledge(report);
    if (!silent) addLog(`외부학습: 소스 ${Number(report.source_count || 0).toLocaleString()}개, 패키지 ${Number(report.package_count || 0).toLocaleString()}개, 평균검증 ${Number(report.avg_validation_score || 0).toFixed(1)}점`);
    return report;
  } catch (error) {
    setText("externalKnowledgeStage", "외부학습 조회 실패");
    const packagesNode = el("#externalKnowledgePackages");
    if (packagesNode) {
      packagesNode.innerHTML = `<article class="blocked"><strong>외부학습 조회 실패</strong><span>${escapeHtml(error.message || "-")}</span></article>`;
    }
    if (!silent) addLog(`외부학습 조회 실패: ${error.message}`);
    return null;
  }
}

async function loadOpsStatus() {
  try {
    const response = await fetch("/api/ops/status/poll");
    const status = await response.json();
    state.lastOpsStatus = status;
    renderAccountDashboard();
    const paper = status.paper || {};
    const approvals = status.approvals || {};
    const duplicate = status.duplicate_guard || {};
    const outbox = status.telegram_outbox || {};
    const policy = status.autotrade_policy || {};
    const readiness = status.autotrade_readiness || {};
    const recentApprovals = approvals.recent || [];
    const latestPending = recentApprovals.find((item) => item.status === "pending") || recentApprovals[0] || {};
    state.lastApprovalToken = latestPending.token || state.lastApprovalToken || "";
    setText("opsState", status.safety || "실전 주문 잠금");
    const pollHealth = status.poll_health || {};
    const serverRuntime = status.server_runtime || {};
    const expectedRuntimeMarker = "ops_status_poll_cache_stabilized";
    const serverRuntimeMarkerMatches = serverRuntime.runtime_marker === expectedRuntimeMarker;
    const serverRuntimeReady = Boolean(serverRuntime.started_at && serverRuntimeMarkerMatches);
    const pollMs = Number(pollHealth.total_step_ms || 0);
    const slowCount = Number(pollHealth.slow_step_count || 0);
    const slowSteps = Array.isArray(pollHealth.slow_steps) ? pollHealth.slow_steps : [];
    const firstSlowStep = slowSteps[0] || {};
    const slowStepLabel = firstSlowStep.name
      ? `${firstSlowStep.name} ${Number(firstSlowStep.ms || 0).toFixed(0)}ms`
      : "";
    const pollHealthText = pollHealth.status === "watch"
      ? `화면 조회 점검 · ${pollMs.toFixed(0)}ms · 느린 단계 ${slowCount}개`
      : `화면 조회 정상 · ${pollMs.toFixed(0)}ms`;
    const pollHealthDisplayText = pollHealth.status === "watch" && slowStepLabel
      ? `\ud654\uba74 \uc870\ud68c \uc810\uac80 \u00b7 ${pollMs.toFixed(0)}ms \u00b7 ${slowStepLabel}`
      : pollHealthText;
    const pollHealthFinalText = serverRuntimeReady
      ? pollHealthDisplayText
      : `${pollHealthDisplayText} \u00b7 \uc11c\ubc84 \uc7ac\uc2dc\uc791 \ub300\uae30`;
    setText("opsPollHealth", pollHealthFinalText);
    const pollHealthNode = el("#opsPollHealth");
    if (pollHealthNode) {
      pollHealthNode.className = `ops-poll-health ${pollHealth.status === "watch" || !serverRuntimeReady ? "watch" : "ok"}`;
      const pollTitleParts = [
        slowSteps.length
          ? slowSteps.map((step) => `${step.name || "-"}: ${Number(step.ms || 0).toFixed(1)}ms`).join(" / ")
          : `poll total ${pollMs.toFixed(1)}ms`,
      ];
      if (serverRuntime.started_at) {
        pollTitleParts.push(`server started ${serverRuntime.started_at}`);
      }
      if (serverRuntime.uptime_seconds !== undefined) {
        pollTitleParts.push(`uptime ${Number(serverRuntime.uptime_seconds || 0).toFixed(0)}s`);
      }
      if (serverRuntime.process_id) {
        pollTitleParts.push(`pid ${serverRuntime.process_id}`);
      }
      if (serverRuntime.runtime_marker) {
        pollTitleParts.push(`marker ${serverRuntime.runtime_marker}`);
      }
      if (!serverRuntimeReady) {
        pollTitleParts.push(`server runtime marker mismatch or missing; expected ${expectedRuntimeMarker}`);
      }
      pollHealthNode.title = pollTitleParts.join(" / ");
    }
    setText("opsPaperEquity", money(paper.equity || 0));
    setText("opsPaperPnl", pct(paper.total_pnl_pct || 0));
    setText("opsPendingApprovals", `${approvals.pending || 0}`);
    setText("opsDuplicateGuard", duplicate.ready ? `${duplicate.fingerprints || 0}개` : "초기화 필요");
    setText("opsTelegramQueued", `${outbox.queued || 0}`);
    const autoEnabled = !policy.emergency_halt && (policy.paper_autopilot_enabled || policy.live_candidate_enabled || policy.live_pilot_enabled);
    const realOrderState = status.safety_state?.real_order || (policy.live_execution_enabled ? "APPROVAL_REQUIRED" : "BLOCKED");
    const realLockText = realOrderState === "READY_TO_SUBMIT"
      ? "전송가능"
      : realOrderState === "APPROVAL_REQUIRED"
        ? (approvals.pending ? "승인대기" : "승인필요")
        : autoEnabled ? "자동켜짐/실전잠금" : "자동꺼짐/실전잠금";
    setText("opsRealLock", realLockText);
    setText("opsAutoMode", policy.emergency_halt ? "자동매매 멈춤" : autoEnabled ? readiness.mode || "자동연구/Paper" : "자동매매 꺼짐");
    setText("opsReadinessScore", `${readiness.score ?? 0}`);
    setText("opsEmergencyState", policy.emergency_halt ? "정지중" : "정상");
    setText("opsOrderLimit", `${Number(policy.max_order_amount || 0).toLocaleString()}원`);
    setText("opsDailyLossLimit", `${Number(policy.max_daily_loss_pct || 0).toFixed(1)}%`);
    if (el("#opsRealLock")) el("#opsRealLock").className = realOrderState === "READY_TO_SUBMIT" ? "up" : realOrderState === "APPROVAL_REQUIRED" ? "flat" : "down";
    if (el("#opsEmergencyState")) el("#opsEmergencyState").className = policy.emergency_halt ? "down" : "up";
    if (el("#opsReadinessScore")) el("#opsReadinessScore").className = Number(readiness.score || 0) >= 80 ? "up" : Number(readiness.score || 0) >= 55 ? "flat" : "down";
    setInputIfIdle("opsPolicyMaxOrder", policy.max_order_amount ?? 2000000);
    setInputIfIdle("opsPolicyMaxDailyOrders", policy.max_daily_orders ?? 20);
    setInputIfIdle("opsPolicyMaxPosition", policy.max_position_pct ?? 10);
    setInputIfIdle("opsPolicyDailyLoss", policy.max_daily_loss_pct ?? 2);
    setInputIfIdle("opsPolicyPilotMaxQty", policy.live_pilot_max_quantity ?? 1);
    setInputIfIdle("opsPolicyPilotCashPct", policy.live_pilot_max_cash_pct ?? 10);
    setInputIfIdle("opsPolicyAutoCashPct", policy.delegated_live_auto_submit_max_cash_pct ?? 30);
    setInputIfIdle("opsPolicyApprovalCashPct", policy.delegated_live_user_approval_above_cash_pct ?? 50);
    setInputIfIdle("opsPolicyDynamicMaxCashPct", policy.live_pilot_dynamic_max_cash_pct ?? policy.live_pilot_max_cash_pct ?? 50);
    updateOpsCapitalRiskBadge(policy);
    if (el("#opsPolicyLivePilot")) el("#opsPolicyLivePilot").checked = Boolean(policy.live_pilot_enabled);
    if (el("#opsPolicyLiveExecution")) el("#opsPolicyLiveExecution").checked = Boolean(policy.live_execution_enabled);
    renderOpsPlaybook(status.ops_playbook || {});
    renderKisFeatureAbsorption(status.kis_feature_absorption || {});
    renderRuntimeStorageCard(status.runtime_storage || {}, status.data_separation || {}, state.hotLogStorage || {});
    renderFeatureHealthCard(status.feature_health || {});
    renderContinuousTrainingLoopStatus(status.continuous_training || {});
    const hotLogAgeMs = Date.now() - Number(state.hotLogStorageLoadedAt || 0);
    if (!state.hotLogStorage || hotLogAgeMs > 60000) {
      loadHotLogStorage(true).catch(() => {});
    }
    const ticketRows = [...(approvals.recent || []), ...(paper.recent_tickets || [])];
    renderOpsList("#opsTicketRows", ticketRows, "주문/승인 티켓 없음");
    renderOpsList("#opsAuditRows", status.audit || [], "감사 로그 없음");
    const livePilotPlanAgeMs = Date.now() - Number(state.livePilotPlanLoadedAt || 0);
    if (!state.lastLivePilotPlan || livePilotPlanAgeMs > 45000) {
      loadLivePilotPlan(true).catch(() => {});
    }
  } catch (error) {
    setText("opsState", "운영 상태 조회 실패");
    addLog(`운영 게이트 조회 실패: ${error.message}`);
  }
}

async function postOps(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "운영 API 실패");
  await loadOpsStatus();
  return result;
}

function highlightPilotTargetButton(buttonId) {
  const target = buttonId ? document.getElementById(buttonId) : null;
  if (!target) {
    addLog("다음 단계 버튼을 찾지 못했습니다. 화면을 새로고침한 뒤 다시 확인해주세요.");
    return;
  }
  document.querySelectorAll(".pilot-target-pulse").forEach((node) => node.classList.remove("pilot-target-pulse"));
  target.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
  target.classList.add("pilot-target-pulse");
  if (typeof target.focus === "function") target.focus({ preventScroll: true });
  addLog(`다음 단계 위치를 표시했습니다: ${target.textContent.trim() || target.placeholder || buttonId}. 이 동작은 실제 주문을 실행하지 않습니다.`);
  window.setTimeout(() => target.classList.remove("pilot-target-pulse"), 3600);
}

function goToCompetitiveAction(pageId, buttonId) {
  if (pageId) switchPage(pageId);
  window.setTimeout(() => highlightPilotTargetButton(buttonId), 80);
}

function renderLiveCandidateDecision(report = {}) {
  const node = el("#liveCandidateDecisionCard");
  if (!node) return;
  if (!report || !report.selected) {
    node.innerHTML = `
      <div class="live-candidate-decision-head">
        <strong>AI 선정근거</strong>
        <span>후보 생성 후 표시됩니다.</span>
      </div>
      <p>아직 기록된 실전 후보 선정 판단이 없습니다. “AI 판단 1주 후보 생성”을 누르면 선택 이유와 대체 후보가 여기에 남습니다.</p>
    `;
    return;
  }
  const selected = report.selected || {};
  const checks = report.checks_summary || {};
  const why = Array.isArray(selected.why_selected) ? selected.why_selected : [];
  const alternatives = Array.isArray(report.alternatives) ? report.alternatives : [];
  const blockedLabels = Array.isArray(checks.blocked_labels) ? checks.blocked_labels : [];
  node.innerHTML = `
    <div class="live-candidate-decision-head">
      <strong>AI 선정근거</strong>
      <span>${escapeHtml(formatDateTimeShort(report.recorded_at || report.plan_generated_at || ""))}</span>
    </div>
    <div class="live-candidate-picked">
      <div>
        <small>선택 종목</small>
        <strong>${escapeHtml(symbolDisplayName(selected.symbol || "-", selected))}</strong>
        <span>${escapeHtml(selected.symbol || "-")} · ${escapeHtml(selected.strategy || "-")}</span>
      </div>
      <div>
        <small>점수/금액</small>
        <strong>${Number(selected.score || 0).toFixed(1)}</strong>
        <span>${formatKrw(selected.estimated_notional || 0)}</span>
      </div>
      <div>
        <small>상태</small>
        <strong class="${report.candidate_ready ? "up" : "down"}">${escapeHtml(report.verdict || "-")}</strong>
        <span>차단 ${Number(checks.blocked_count || 0)} · 주의 ${Number(checks.warning_count || 0)}</span>
      </div>
    </div>
    ${why.length ? `
      <div class="live-candidate-reasons">
        <b>왜 골랐나</b>
        ${why.slice(0, 5).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
      </div>
    ` : ""}
    <div class="live-candidate-alternatives">
      <b>대체 후보와 제외 이유</b>
      ${alternatives.length ? alternatives.slice(0, 5).map((row) => `
        <article>
          <strong>${escapeHtml(symbolDisplayName(row.symbol || "-", row))}</strong>
          <small>${escapeHtml(row.symbol || "-")} · 점수 ${Number(row.score || 0).toFixed(1)} · ${row.estimated_notional ? formatKrw(row.estimated_notional) : "금액 대기"}</small>
          <span>${escapeHtml(row.decision_note || "우선순위 낮음")}</span>
        </article>
      `).join("") : `<article><strong>대체 후보 없음</strong><small>후보 풀이 비었거나 단일 후보 판단입니다.</small><span>AI 후보 발굴을 갱신하면 비교군이 늘어납니다.</span></article>`}
    </div>
    ${blockedLabels.length ? `<p class="live-candidate-blocks">먼저 확인할 차단 조건: ${blockedLabels.slice(0, 4).map(escapeHtml).join(", ")}</p>` : ""}
  `;
}

async function loadLiveCandidateDecisions(silent = true) {
  const ageMs = Date.now() - Number(state.liveCandidateDecisionLoadedAt || 0);
  if (silent && state.lastLiveCandidateDecision && ageMs < 45000) {
    renderLiveCandidateDecision(state.lastLiveCandidateDecision);
    return state.lastLiveCandidateDecision;
  }
  if (silent && state.liveCandidateDecisionLoading) return state.lastLiveCandidateDecision;
  state.liveCandidateDecisionLoading = true;
  try {
    const response = await fetch("/api/ops/live-candidate-decisions?limit=1");
    const result = await response.json();
    const report = Array.isArray(result.decisions) ? result.decisions[0] : null;
    state.lastLiveCandidateDecision = report || {};
    state.liveCandidateDecisionLoadedAt = Date.now();
    renderLiveCandidateDecision(report || {});
    return report;
  } catch (error) {
    renderLiveCandidateDecision({});
    if (!silent) addLog(`AI 선정근거 조회 실패: ${error.message}`);
    return null;
  } finally {
    state.liveCandidateDecisionLoading = false;
  }
}

function renderLiveReasonBackfills(payload = {}) {
  const node = el("#liveReasonBackfillCard");
  if (!node) return;
  const current = payload.current || {};
  const summary = payload.summary || current.summary || {};
  const latest = Array.isArray(payload.backfills) ? payload.backfills[0] : null;
  const items = Array.isArray(current.items) && current.items.length
    ? current.items
    : (Array.isArray(latest?.items) ? latest.items : []);
  const createdAt = current.created_at || latest?.created_at || "";
  const total = Number(summary.total || 0);
  const low = Number(summary.low || 0) + Number(summary.unknown || 0);
  const medium = Number(summary.medium || 0);
  const itemCount = Number(current.item_count ?? latest?.item_count ?? items.length ?? 0);
  const notePath = current.note_path || latest?.note_path || "";
  const memoryLatest = current.memory || payload.memory_summary?.latest || latest?.memory || {};
  const memoryCount = Number(payload.memory_summary?.count || (memoryLatest?.id ? 1 : 0));
  const memoryOccurrence = Number(memoryLatest?.occurrence_count || 0);
  const memoryState = memoryLatest?.id
    ? `${memoryLatest.deduplicated ? "기존 기억 갱신" : "기억됨"} · ${escapeHtml(memoryLatest.id)}${memoryOccurrence ? ` · 반복 ${memoryOccurrence}회` : ""}`
    : "장기기억 대기";
  node.innerHTML = `
    <div class="live-candidate-decision-head">
      <strong>매매 근거 보강</strong>
      <span>${createdAt ? escapeHtml(formatDateTimeShort(createdAt)) : "복기 대기"}</span>
    </div>
    <div class="live-reason-backfill-summary">
      <div><b>${itemCount}</b><small>보강 대상</small></div>
      <div><b class="${low ? "down" : "up"}">${low}</b><small>낮은 근거</small></div>
      <div><b>${medium}</b><small>보통 근거</small></div>
      <div><b>${total}</b><small>검토 매매</small></div>
    </div>
    <p>${escapeHtml(summary.headline || "실전 매매 근거 품질을 확인하는 중입니다.")}</p>
    <div class="live-reason-backfill-list">
      ${items.length ? items.slice(0, 4).map((item) => `
        <article>
          <strong>${escapeHtml(item.name || item.symbol || "종목")}</strong>
          <small>${escapeHtml(item.symbol || "-")} · ${escapeHtml(item.grade || item.severity || "-")} · ${escapeHtml(item.status || "-")} · 매수 ${escapeHtml(formatDateTimeShort(item.buy_at || ""))}</small>
          <span>${escapeHtml(item.backfill_action || "다음 매매부터 후보 비교, 매수가 기준, 손절/익절 기준을 함께 남깁니다.")}</span>
        </article>
      `).join("") : `<article><strong>보강 대상 없음</strong><small>낮은 품질의 실전 매매 근거가 없습니다.</small><span>새 실전 매매가 생기면 자동으로 복기 후보를 다시 계산합니다.</span></article>`}
    </div>
    <div class="live-reason-backfill-actions">
      <button id="saveLiveReasonBackfill" type="button">현재 보강 리포트 저장</button>
      <small>${notePath ? `노트: ${escapeHtml(notePath)}` : "실제 주문 없이 복기 기록만 저장합니다."}</small>
      <small>장기기억: ${memoryState} · 누적 ${memoryCount}개</small>
    </div>
  `;
}

async function loadLiveReasonBackfills(silent = true) {
  try {
    const response = await fetch("/api/ops/live-reason-backfills?limit=1");
    const result = await response.json();
    renderLiveReasonBackfills(result);
    return result;
  } catch (error) {
    renderLiveReasonBackfills({});
    if (!silent) addLog(`매매 근거 보강 조회 실패: ${error.message}`);
    return null;
  }
}

async function saveLiveReasonBackfill() {
  const button = el("#saveLiveReasonBackfill");
  if (button) {
    button.disabled = true;
    button.textContent = "저장 중";
  }
  try {
    const response = await fetch("/api/ops/live-reason-backfills", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "ui-live-reason-backfill-card" }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || result.message || "보강 리포트 저장 실패");
    renderLiveReasonBackfills({ ok: true, current: result, summary: result.summary || {}, backfills: [result] });
    addLog(`매매 근거 보강 리포트 저장: ${result.item_count || 0}건`);
    return result;
  } catch (error) {
    addLog(`매매 근거 보강 리포트 저장 실패: ${error.message}`);
    return null;
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "현재 보강 리포트 저장";
    }
  }
}

function renderTodayTradeQuickSummary(payload = {}) {
  const node = el("#todayTradeQuickCard");
  if (!node) return;
  const counts = payload.counts || {};
  const why = payload.why_no_real_trade || {};
  const whyAction = why.recommended_action || {};
  const alternateAction = why.alternate_action || {};
  const diagnostics = Array.isArray(why.diagnostics) ? why.diagnostics : [];
  const whyLatest = why.latest || {};
  const broker = payload.broker_executions || state.todayBrokerExecutions || {};
  const brokerExecutions = Array.isArray(broker.executions) ? broker.executions : [];
  const brokerMessage = broker.message || (broker.count == null ? "실제 체결 조회를 준비 중입니다." : "읽기전용 체결 조회 완료");
  const whyClass = String(why.status || "idle").replaceAll("_", "-");
  const reasonText = String(why.reason || "");
  const nextText = String(why.next || "");
  const actionDetail = String(whyAction.detail || "");
  const showActionDetail = actionDetail
    && !actionDetail.startsWith(reasonText)
    && !nextText.includes(actionDetail);
  const groups = [
    { key: "live_submitted", label: "실전 전송", tone: Number(counts.live_submitted || 0) ? "up" : "" },
    { key: "live_blocked", label: "차단", tone: Number(counts.live_blocked || 0) ? "down" : "" },
    { key: "live_candidates", label: "실전 후보", tone: Number(counts.live_candidates || 0) ? "warn" : "" },
    { key: "paper_filled", label: "모의체결", tone: Number(counts.paper_filled || 0) ? "paper" : "" },
  ];
  const rows = [
    ...(Array.isArray(payload.live_submitted) ? payload.live_submitted.map((item) => ({ ...item, type: "실전" })) : []),
    ...(Array.isArray(payload.live_blocked) ? payload.live_blocked.map((item) => ({ ...item, type: "차단" })) : []),
    ...(Array.isArray(payload.live_candidates) ? payload.live_candidates.map((item) => ({ ...item, type: "후보" })) : []),
    ...(Array.isArray(payload.dry_ready) ? payload.dry_ready.map((item) => ({ ...item, type: "Dry" })) : []),
    ...(Array.isArray(payload.paper_filled) ? payload.paper_filled.map((item) => ({ ...item, type: "모의" })) : []),
  ];
  node.innerHTML = `
    <div class="live-candidate-decision-head">
      <strong>오늘 매매 요약</strong>
      <span>${escapeHtml(payload.date || "오늘")} · ${escapeHtml(payload.generated_at ? formatDateTimeShort(payload.generated_at) : "갱신 대기")}</span>
    </div>
    <div class="today-trade-readonly-banner">
      <b>조회 전용</b>
      <span>이 영역의 버튼은 로컬 원장과 한투 체결만 확인합니다. 매수·매도 주문은 보내지 않습니다.</span>
    </div>
    <div class="today-trade-source-note">
      <span>로컬 원장 기준</span>
      <small>한투 실제 체결 여부는 체결 조회로 별도 확인합니다. 이 카드는 주문을 실행하지 않습니다.</small>
    </div>
    <div class="today-trade-broker-note ${broker.ok === false ? "error" : ""}">
      <span>한투 실제 체결</span>
      <b>${broker.ok === false ? "조회 실패" : broker.count == null ? "조회 중" : `${Number(broker.count || 0).toLocaleString()}건`}</b>
      <small>${escapeHtml(`${brokerMessage}${broker.generated_at ? ` · ${formatDateTimeShort(broker.generated_at)}` : ""}`)}</small>
    </div>
    ${brokerExecutions.length ? `
      <div class="today-trade-broker-list">
        ${brokerExecutions.slice(0, 3).map((row) => `
          <article>
            <b>${escapeHtml(row.side_label || row.side_name || row.side || "-")}</b>
            <span>${escapeHtml(row.line || "-")}</span>
            <small>${escapeHtml(row.executed_at ? formatDateTimeShort(row.executed_at) : row.ordered_at ? formatDateTimeShort(row.ordered_at) : "-")} · 한투 실제 체결</small>
          </article>
        `).join("")}
      </div>
    ` : ""}
    <div class="today-trade-quick-summary">
      ${groups.map((group) => `
        <div>
          <b class="${group.tone}">${Number(counts[group.key] || 0).toLocaleString()}</b>
          <small>${escapeHtml(group.label)}</small>
        </div>
      `).join("")}
    </div>
    <div class="today-trade-glossary">
      <span><b>실전 전송</b> 브로커에 주문을 보낸 기록</span>
      <span><b>한투 실제 체결</b> 증권사 체결 내역</span>
      <span><b>차단</b> 안전장치가 주문을 멈춘 기록</span>
      <span><b>모의체결</b> AI 훈련 장부 기록</span>
    </div>
    <div class="today-trade-why ${escapeHtml(whyClass)}">
      <b>${escapeHtml(why.title || "오늘 실전 매매 이유 분석")}</b>
      <span>${escapeHtml(why.reason || "오늘 실전 전송 여부를 분석하는 중입니다.")}</span>
      ${whyLatest.line ? `
        <em>최근 기록: ${escapeHtml(whyLatest.line)}${whyLatest.created_at ? ` · ${escapeHtml(formatDateTimeShort(whyLatest.created_at))}` : ""}</em>
      ` : ""}
      <small>${escapeHtml(why.next || "이 카드는 조회만 하며 주문은 실행하지 않습니다.")}</small>
      ${showActionDetail ? `<small class="today-trade-action-detail">${escapeHtml(actionDetail)}</small>` : ""}
      ${diagnostics.length ? `
        <div class="today-trade-diagnostics">
          ${diagnostics.slice(0, 3).map((item) => `
            <article class="${escapeHtml(item.level || "info")}">
              <b>${escapeHtml(item.title || "진단")}</b>
              <span>${escapeHtml(item.detail || "-")}</span>
              ${item.action ? `<small>${escapeHtml(item.action)}</small>` : ""}
              ${item.button_id ? `
                <button type="button" data-pilot-target-button="${escapeHtml(item.button_id)}">
                  ${escapeHtml(item.button_label || "관련 버튼 찾기")}
                </button>
              ` : ""}
            </article>
          `).join("")}
        </div>
      ` : ""}
      ${whyAction.button_id ? `
        <button type="button" data-pilot-target-button="${escapeHtml(whyAction.button_id)}">
          ${escapeHtml(whyAction.button_label || whyAction.label || "다음 버튼 찾기")}
        </button>
      ` : ""}
      ${alternateAction.button_id && alternateAction.button_id !== whyAction.button_id ? `
        <button type="button" data-pilot-target-button="${escapeHtml(alternateAction.button_id)}">
          ${escapeHtml(alternateAction.button_label || "대체 버튼 찾기")}
        </button>
      ` : ""}
    </div>
    <p>${escapeHtml(payload.headline || "오늘 매매 기록을 확인하는 중입니다.")}</p>
    <div class="today-trade-quick-list">
      ${rows.length ? rows.slice(0, 8).map((row) => `
        <article>
          <b>${escapeHtml(row.type || "-")}</b>
          <span>${escapeHtml(row.line || `${row.name || row.symbol || "-"} ${row.side_label || row.side || ""}`)}</span>
          <small>${escapeHtml(row.created_at ? formatDateTimeShort(row.created_at) : "-")} · ${escapeHtml(row.real_execution_label || row.mode_label || row.status_label || "-")} · ${escapeHtml(row.source || "-")}</small>
        </article>
      `).join("") : `
        <article class="empty">
          <b>오늘 기록 없음</b>
          <span>실전 전송, 실전 후보, 모의체결 기록이 아직 없습니다.</span>
          <small>이 카드는 조회만 하며 주문은 실행하지 않습니다.</small>
        </article>
      `}
    </div>
    <div class="live-reason-backfill-actions">
      <button id="refreshTodayTradesInline" type="button">오늘 매매 다시 확인</button>
      <small>${escapeHtml(payload.safety || "읽기전용 요약입니다. 실제 주문은 실행하지 않습니다.")}</small>
    </div>
  `;
}

function compactKisExecution(row = {}) {
  const symbol = String(row.symbol || "").trim().toUpperCase();
  const name = row.name || symbolDisplayName(symbol);
  const side = String(row.side || "").toUpperCase();
  const sideLabel = side === "SELL" ? "매도" : side === "BUY" ? "매수" : String(row.side_name || side || "-");
  const quantity = Number(row.filled_quantity || row.quantity || 0);
  const price = Number(row.avg_price || row.price || 0);
  const amount = Number(row.amount || (quantity && price ? quantity * price : 0));
  const priceText = price ? ` @ ${price.toLocaleString()}원` : "";
  const amountText = amount ? ` · ${amount.toLocaleString()}원` : "";
  return {
    symbol,
    name,
    side,
    side_label: sideLabel,
    quantity,
    price,
    amount,
    ordered_at: row.ordered_at || "",
    executed_at: row.executed_at || row.ordered_at || "",
    order_no: row.order_no || "",
    line: `${name} ${sideLabel} ${quantity ? `${quantity.toLocaleString()}주` : ""}${priceText}${amountText}`.trim(),
  };
}

function fetchJsonWithTimeout(url, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { signal: controller.signal })
    .then(async (response) => ({ response, data: await response.json() }))
    .finally(() => window.clearTimeout(timer));
}

async function loadKisTodayExecutionsSummary(dateText, force = false) {
  const now = Date.now();
  if (!force && state.todayBrokerExecutions && now - state.todayBrokerExecutionsFetchedAt < 90000) {
    return state.todayBrokerExecutions;
  }
  try {
    const date = encodeURIComponent(dateText || new Date().toISOString().slice(0, 10));
    const { response, data } = await fetchJsonWithTimeout(`/api/kis/executions?date=${date}&filled=all`, 10000);
    if (!response.ok || data.ok === false) throw new Error(data.message || data.error || "한투 체결 조회 실패");
    const message = String(data.message || "").trim();
    const executions = Array.isArray(data.executions)
      ? data.executions.slice(-3).reverse().map((row) => compactKisExecution(row))
      : [];
    state.todayBrokerExecutions = {
      ok: true,
      count: Number(data.count || 0),
      message: message || (Number(data.count || 0) ? "실제 체결 기록 있음" : "실제 체결 기록 없음"),
      executions,
      generated_at: new Date().toISOString(),
    };
  } catch (error) {
    state.todayBrokerExecutions = {
      ok: false,
      count: null,
      message: error.name === "AbortError" ? "한투 체결 조회 시간 초과" : error.message,
      executions: [],
      generated_at: new Date().toISOString(),
    };
  }
  state.todayBrokerExecutionsFetchedAt = Date.now();
  return state.todayBrokerExecutions;
}

async function loadTodayTradeQuickSummary(silent = true) {
  try {
    const response = await fetch("/api/ops/today-trades/quick");
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || result.message || "오늘 매매 요약 조회 실패");
    renderTodayTradeQuickSummary(result);
    loadKisTodayExecutionsSummary(result.date, !silent).then((broker) => {
      renderTodayTradeQuickSummary({ ...result, broker_executions: broker });
    });
    if (!silent) addLog(`오늘 매매 요약: ${result.headline || "-"}`);
    return result;
  } catch (error) {
    renderTodayTradeQuickSummary({
      headline: `오늘 매매 요약 조회 실패: ${error.message}`,
      counts: {},
      safety: "조회 실패입니다. 실제 주문은 실행하지 않았습니다.",
    });
    if (!silent) addLog(`오늘 매매 요약 조회 실패: ${error.message}`);
    return null;
  }
}

function renderLiveAccountChanges(payload = {}) {
  const node = el("#liveAccountChangeSummary");
  if (!node) return;
  state.liveAccountChanges = payload;
  const current = payload.current || {};
  const changes = Array.isArray(payload.changes) ? payload.changes : [];
  const hasChange = Boolean(payload.has_change);
  const hasPrevious = Boolean(payload.has_previous);
  const ok = payload.ok !== false;
  const statusClass = ok ? (hasChange ? "changed" : "stable") : "error";
  const statusText = !ok
    ? "조회 실패"
    : hasChange
      ? "변화 감지"
      : hasPrevious
        ? "변화 없음"
        : "기준 저장";
  const detectedAt = payload.detected_at ? formatDateTimeShort(payload.detected_at) : "조회 대기";
  const moneyText = (value) => `${Number(value || 0).toLocaleString()}원`;
  const numberText = (value) => Number(value || 0).toLocaleString();
  const changeRows = changes.slice(0, 6).map((item) => {
    if (item.symbol) {
      const name = item.name || symbolDisplayName(item.symbol || "");
      const before = numberText(item.before_quantity);
      const after = numberText(item.after_quantity);
      const delta = Number(item.delta_quantity || 0);
      return `
        <li>
          <b>${escapeHtml(name)}</b>
          <span>수량 ${escapeHtml(before)}주 → ${escapeHtml(after)}주</span>
          <small>${escapeHtml(delta > 0 ? "매수/입고 가능성" : "매도/출고 가능성")} · 변화 ${escapeHtml(delta > 0 ? `+${numberText(delta)}` : numberText(delta))}주</small>
        </li>
      `;
    }
    const before = Number(item.before || 0);
    const after = Number(item.after || 0);
    const delta = Number(item.delta || 0);
    return `
      <li>
        <b>${escapeHtml(item.label || item.type || "계좌 항목")}</b>
        <span>${escapeHtml(moneyText(before))} → ${escapeHtml(moneyText(after))}</span>
        <small>변화 ${escapeHtml(delta >= 0 ? `+${moneyText(delta)}` : moneyText(delta))}</small>
      </li>
    `;
  }).join("");
  node.innerHTML = `
    <div class="${statusClass}">
      <b>실계좌 변화 감지</b>
      <strong>${escapeHtml(statusText)}</strong>
      <small>${escapeHtml(payload.message || "한투 계좌 스냅샷을 읽기전용으로 비교합니다.")} · ${escapeHtml(detectedAt)}</small>
    </div>
    <div>
      <span>${escapeHtml(moneyText(current.available_cash))}</span>
      <small>주문가능현금</small>
    </div>
    <div>
      <span>${escapeHtml(numberText(current.position_count))}개</span>
      <small>보유 종목</small>
    </div>
    ${changeRows ? `<ul>${changeRows}</ul>` : `
      <p>${escapeHtml(hasPrevious ? "최근 감지된 수동 매매/입금 변화가 없습니다." : "이번 조회를 기준 스냅샷으로 저장했습니다. 다음 조회부터 변화가 비교됩니다.")}</p>
    `}
  `;
}

async function loadLiveAccountChanges(silent = false) {
  try {
    const response = await fetch("/api/ops/live-account/changes?refresh=1");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || result.message || "실계좌 변화 감지 실패");
    renderLiveAccountChanges(result);
    if (!silent) {
      addLog(`실계좌 변화 감지: ${result.message || "-"} · 변화 ${Number(result.change_count || 0).toLocaleString()}건 · 읽기전용`);
    }
    return result;
  } catch (error) {
    const fallback = {
      ok: false,
      message: `실계좌 변화 감지 실패: ${error.message}`,
      current: {},
      changes: [],
      safety: "조회 실패입니다. 실제 주문은 실행하지 않았습니다.",
    };
    renderLiveAccountChanges(fallback);
    if (!silent) addLog(`실계좌 변화 감지 실패: ${error.message}`);
    return null;
  }
}

function renderMissedBuyReview(payload = {}) {
  const node = el("#missedBuyReviewCard");
  if (!node) return;
  const counts = payload.counts || {};
  const rows = Array.isArray(payload.reviewed) ? payload.reviewed : [];
  const generated = payload.generated_at ? formatDateTimeShort(payload.generated_at) : "조회 대기";
  node.innerHTML = `
    <div class="live-candidate-decision-head">
      <strong>오늘 놓친 매수 복기</strong>
      <span>${escapeHtml(payload.work_date || payload.target_date || "오늘")} · ${escapeHtml(generated)}</span>
    </div>
    <p>${escapeHtml(payload.lesson || "강했는데 실제 매수하지 못한 종목을 조회합니다. 버튼을 누르면 읽기전용으로 복기합니다.")}</p>
    <div class="today-trade-quick-summary">
      <div><b class="${Number(counts.reviewed || 0) ? "warn" : ""}">${Number(counts.reviewed || 0).toLocaleString()}</b><small>놓친 후보</small></div>
      <div><b class="${Number(counts.live_buy_submitted || 0) ? "up" : ""}">${Number(counts.live_buy_submitted || 0).toLocaleString()}</b><small>실제 매수</small></div>
      <div><b>${Number(counts.live_buy_candidates || 0).toLocaleString()}</b><small>매수 후보</small></div>
      <div><b>${Number(counts.strong_rows || 0).toLocaleString()}</b><small>강한 종목</small></div>
    </div>
    <div class="missed-buy-review-list">
      ${rows.length ? rows.slice(0, 6).map((row) => `
        <article>
          <strong>${escapeHtml(row.name || symbolDisplayName(row.symbol || ""))}</strong>
          <b>${pct(row.change_pct || 0)} · 거래대금 ${Number(row.amount_eok || 0).toLocaleString()}억 · 점수 ${Number(row.score || 0).toFixed(1)}</b>
          <span>${escapeHtml(row.not_bought_reason || "매수하지 못한 이유 분석 대기")}</span>
          <small>${escapeHtml(row.detail || "-")}</small>
          <em>다음 보완: ${escapeHtml(row.next_fix || payload.next_action || "-")}</em>
        </article>
      `).join("") : `
        <article>
          <strong>복기 후보 대기</strong>
          <span>버튼을 누르면 오늘 강했던 종목과 실제 매수/후보 로그를 비교합니다.</span>
          <small>읽기전용 복기라 주문은 실행하지 않습니다.</small>
        </article>
      `}
    </div>
    <button id="refreshMissedBuyReview" type="button">오늘 놓친 매수 복기</button>
    <small>${escapeHtml(payload.safety || "읽기전용 복기입니다. 실제 주문은 실행하지 않습니다.")}</small>
  `;
}

async function loadMissedBuyReview(silent = true) {
  const button = el("#refreshMissedBuyReview");
  try {
    if (button) {
      button.disabled = true;
      button.textContent = "놓친 매수 복기 중";
    }
    const response = await fetch("/api/research/missed-buy-review?limit=10&source=ui-missed-buy-review");
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.error || "놓친 매수 후보 복기 실패");
    state.lastMissedBuyReview = result;
    renderMissedBuyReview(result);
    if (!silent) addLog(`오늘 놓친 매수 복기: ${result.lesson || ""}`);
    return result;
  } catch (error) {
    renderMissedBuyReview({
      ok: false,
      lesson: `놓친 매수 후보 복기 실패: ${error.message}`,
      counts: {},
      reviewed: [],
      safety: "조회 실패입니다. 실제 주문은 실행하지 않았습니다.",
    });
    if (!silent) addLog(`오늘 놓친 매수 복기 실패: ${error.message}`);
    return null;
  } finally {
    const nextButton = el("#refreshMissedBuyReview");
    if (nextButton) {
      nextButton.disabled = false;
      nextButton.textContent = "오늘 놓친 매수 복기";
    }
  }
}

function renderLiveOrderBlackbox(payload = {}) {
  const node = el("#liveOrderBlackboxCard");
  if (!node) return;
  const counts = payload.counts || {};
  const records = Array.isArray(payload.records) ? payload.records : [];
  const createdAt = payload.created_at || "";
  node.innerHTML = `
    <div class="live-candidate-decision-head">
      <strong>실전 주문 블랙박스</strong>
      <span>${createdAt ? escapeHtml(formatDateTimeShort(createdAt)) : "주문 추적 대기"}</span>
    </div>
    <div class="live-order-blackbox-summary">
      <div><b>${Number(counts.total || 0)}</b><small>검토 주문</small></div>
      <div><b class="${Number(counts.submitted || 0) ? "up" : ""}">${Number(counts.submitted || 0)}</b><small>실전 전송</small></div>
      <div><b class="${Number(counts.blocked || 0) ? "down" : ""}">${Number(counts.blocked || 0)}</b><small>차단</small></div>
      <div><b class="${Number(counts.quality_low || 0) ? "down" : "up"}">${Number(counts.quality_low || 0)}</b><small>근거 보강</small></div>
    </div>
    <p>${escapeHtml(payload.headline || "최근 실전 주문의 근거, 게이트, 체결/복기 상태를 묶어 확인합니다.")}</p>
    <div class="live-order-blackbox-list">
      ${records.length ? records.slice(0, 5).map((item) => {
        const quality = item.quality || {};
        const gate = item.gate || {};
        const perf = item.performance || {};
        const snapshot = item.context_snapshot || {};
        const chart = snapshot.chart || {};
        const sector = snapshot.sector || {};
        const theme = sector.theme || {};
        const news = snapshot.news || {};
        const financial = snapshot.financial || {};
        const klass = quality.level === "high" ? "good" : quality.level === "medium" ? "warn" : "bad";
        const price = Number(item.price || 0);
        const qty = Number(item.quantity || 0);
        const amount = Number(chart.amount_estimate || item.amount || 0);
        const volumeRatio = Number(chart.volume_ratio20 || 0);
        const modeLabel = snapshot.mode === "order_time" ? "주문시점" : snapshot.mode === "reconstructed" ? "재구성" : "스냅샷";
        return `
          <article class="${klass}">
            <div>
              <strong>${escapeHtml(item.name || symbolDisplayName(item.symbol || ""))}</strong>
              <b>${escapeHtml(item.side_label || item.side || "-")} ${qty ? `${qty.toLocaleString()}주` : ""}</b>
            </div>
            <small>${escapeHtml(item.symbol || "-")} · ${escapeHtml(item.status || "-")} · ${price ? `${price.toLocaleString()}원` : "-"} · ${escapeHtml(perf.label || "주문 로그")}</small>
            <span>근거품질: ${escapeHtml(quality.label || item.reason_quality?.grade || "-")} · 게이트 통과 ${Number(gate.passed || 0)}/${Number(gate.total || 0)} · 차단 ${Number(gate.blocked || 0)}</span>
            <span>차트: ${escapeHtml(modeLabel)} · ${escapeHtml(chart.trend || "추세 확인 필요")} · 5일 ${pct(chart.return_5d_pct || 0)} · 20일 ${pct(chart.return_20d_pct || 0)} · 거래대금 ${amount ? money0(amount) : "-"}</span>
            <span>섹터/뉴스: ${escapeHtml(theme.theme || news.stance || "-")} · ${escapeHtml(news.summary || theme.theme_detail || "뉴스 스냅샷 부족")}</span>
            <span>재무: ${escapeHtml(financial.stance || "-")} · 점수 ${Number(financial.score || 0).toFixed(0)} · 거래량비 ${volumeRatio ? `${volumeRatio.toFixed(2)}배` : "-"}</span>
            <em>${escapeHtml(item.reason || item.selection_reason || "근거 기록 없음")}</em>
          </article>
        `;
      }).join("") : `<article class="empty"><strong>주문 로그 없음</strong><small>아직 블랙박스로 묶을 실전 주문 기록이 없습니다.</small><span>실전 후보/승인/전송 흐름이 생기면 자동으로 표시됩니다.</span></article>`}
    </div>
    <div class="live-reason-backfill-actions">
      <button id="saveLiveOrderBlackbox" type="button">현재 블랙박스 스냅샷 저장</button>
      <small>${escapeHtml(payload.safety || "조회/분석 전용입니다. 실제 주문은 실행하지 않습니다.")}</small>
    </div>
  `;
}

function renderTradeOperatorFocusCard(focus = {}) {
  const focusItems = Array.isArray(focus.focus_items) ? focus.focus_items : [];
  const tone = String(focus.tone || (focus.ok === false ? "block" : "safe")).replace(/[^a-z0-9_-]/gi, "-").toLowerCase();
  const progress = Math.max(0, Math.min(Number(focus.progress_pct || 0), 100));
  if (!focusItems.length && !focus.task && !focus.detail) return "";
  return `
    <div class="trade-operator-focus ${escapeHtml(tone)}">
      <div class="trade-operator-focus-head">
        <div>
          <strong>매매직원 현재 초점 <em>${escapeHtml(focus.state || "감시 중")}</em></strong>
          <span>${escapeHtml(focus.task || "조건검색·분봉·주문 단계 확인 중")}</span>
          <small>${escapeHtml(focus.detail || focus.evidence || "매매직원이 무엇을 보고 있는지 읽기전용으로 정리합니다.")}</small>
        </div>
        <div>
          <b>${progress.toFixed(0)}%</b>
          <small>${escapeHtml(focus.target || "시장 전체")}</small>
        </div>
      </div>
      <div class="trade-operator-focus-items">
        ${focusItems.map((item) => `
          <span class="${escapeHtml(String(item.tone || "wait").replace(/[^a-z0-9_-]/gi, "-").toLowerCase())}">
            <small>${escapeHtml(item.label || "-")}</small>
            <b>${escapeHtml(item.value || "-")}</b>
            <em>${escapeHtml(item.detail || "-")}</em>
          </span>
        `).join("")}
      </div>
      <div class="trade-operator-focus-next">
        <span>${escapeHtml(focus.evidence || "근거 수집 중")}</span>
        <b>${escapeHtml(focus.next_action || "상위 후보도 바로 주문하지 않고 안전 게이트를 다시 확인합니다.")}</b>
      </div>
    </div>
  `;
}

function renderTradeBlockerSnapshot(snapshot = {}) {
  const node = el("#tradeBlockerSnapshot");
  if (!node) return;
  const state = String(snapshot.state || "WAIT").toLowerCase();
  const checks = Array.isArray(snapshot.checks) ? snapshot.checks : [];
  const policy = snapshot.policy || {};
  const market = snapshot.market || {};
  const workflow = snapshot.workflow || {};
  const approvalIssue = workflow.approval_issue || {};
  const recommended = snapshot.recommended_next || {};
  const preflight = snapshot.preflight || {};
  const orderQuota = snapshot.order_quota || preflight.order_quota || {};
  const quotaItems = Array.isArray(orderQuota.items) ? orderQuota.items : [];
  const executionAwareness = snapshot.execution_awareness || preflight.execution_awareness || {};
  const reconciliationAwareness = snapshot.reconciliation_awareness || preflight.reconciliation_awareness || {};
  const operatorFocus = snapshot.operator_focus || preflight.operator_focus || {};
  const orderStateMachine = snapshot.order_state_machine || preflight.order_state_machine || {};
  const preflightItems = Array.isArray(preflight.items) ? preflight.items : [];
  const preflightScore = Number(preflight.score || 0);
  const passCount = Number(preflight.pass_count || checks.filter((item) => item.status === "pass").length);
  const waitCount = Number(preflight.wait_count || checks.filter((item) => item.status === "wait").length);
  const blockCount = Number(preflight.block_count || checks.filter((item) => item.status === "block").length);
  const workflowClass = workflow.requires_final_confirm ? "submit-ready" : String(workflow.stage || "").replaceAll("_", "-");
  node.className = `trade-blocker-card ${state} ${workflowClass}`;
  node.innerHTML = `
    <div class="trade-blocker-head">
      <strong>왜 매매 안 하나</strong>
      <span>${escapeHtml(snapshot.headline || "빠른 진단 대기")}</span>
    </div>
    <p>${escapeHtml(snapshot.next_action || snapshot.safety || "정책과 시장 시간을 확인하는 중입니다.")}</p>
    <div class="trade-now-action ${escapeHtml(preflight.tone || state || "wait")}">
      <div>
        <small>현재 할 일</small>
        <strong>${escapeHtml(recommended.label || snapshot.headline || "상태 점검")}</strong>
        <span>${escapeHtml(recommended.detail || preflight.next || snapshot.next_action || "점검 결과를 확인하세요.")}</span>
      </div>
      <div class="trade-now-counts">
        <b class="pass">${passCount}</b><small>통과</small>
        <b class="wait">${waitCount}</b><small>대기</small>
        <b class="block">${blockCount}</b><small>차단</small>
      </div>
      ${recommended.button_id ? `<button type="button" data-pilot-target-button="${escapeHtml(recommended.button_id)}">${escapeHtml(recommended.button_label || "지금 누를 버튼 찾기")}</button>` : ""}
    </div>
    ${quotaItems.length ? `
      <div class="trade-quota-strip">
        <div class="trade-quota-head">
          <strong>오늘 자동 주문 한도</strong>
          <div>
            <b>${escapeHtml(orderQuota.reset_in_label || "초기화 대기")}</b>
            <span>${escapeHtml(orderQuota.summary || "한도 확인 중")}</span>
          </div>
        </div>
        <div class="trade-quota-items">
          ${quotaItems.map((item) => {
            const used = Number(item.used || 0);
            const max = Number(item.max || 0);
            const remaining = Number(item.remaining || 0);
            const ratio = max > 0 ? (used / max) * 100 : 100;
            return `
              <article class="${escapeHtml(item.tone || (remaining > 0 ? "pass" : "block"))}">
                <b>${escapeHtml(item.side_label || "-")}</b>
                <strong>${used.toLocaleString()} / ${max.toLocaleString()}회</strong>
                <i><span style="width:${Math.max(0, Math.min(ratio, 100)).toFixed(1)}%"></span></i>
                <small>남음 ${remaining.toLocaleString()}회 · ${escapeHtml(item.message || "")}</small>
              </article>
            `;
          }).join("")}
        </div>
        <small>${escapeHtml(orderQuota.safety || "한도는 자동운용 안전장치입니다.")}</small>
      </div>
    ` : ""}
    ${renderTradeOperatorFocusCard(operatorFocus)}
    ${executionAwareness.message || executionAwareness.latest_line ? `
      <div class="trade-execution-awareness ${escapeHtml(executionAwareness.tone || "wait")} ${escapeHtml(executionAwareness.freshness_tone || "wait")}">
        <div>
          <strong>한투 체결 감지 <em>${escapeHtml(executionAwareness.freshness_state || "확인 중")}</em></strong>
          <span>${escapeHtml(executionAwareness.latest_line || executionAwareness.message || "체결 조회 대기")}</span>
          ${executionAwareness.realized_line ? `<small>${escapeHtml(executionAwareness.realized_line)}</small>` : ""}
        </div>
        <div>
          <b>${executionAwareness.ok ? `${Number(executionAwareness.count || 0).toLocaleString()}건` : "대기"}</b>
          <small>${executionAwareness.journal_ok ? "매매일지 저장됨" : "매매일지 대기"} · ${escapeHtml(executionAwareness.age_label || "시각 대기")}</small>
        </div>
        <em>${escapeHtml(executionAwareness.next || "읽기전용 체결 조회 상태입니다.")}</em>
      </div>
    ` : ""}
    ${reconciliationAwareness.message || reconciliationAwareness.headline ? `
      <div class="trade-execution-awareness trade-reconciliation-awareness ${escapeHtml(reconciliationAwareness.tone || "wait")} ${escapeHtml(reconciliationAwareness.check_status || "wait")}">
        <div>
          <strong>체결/잔고 대조 <em>${escapeHtml(reconciliationAwareness.status || "확인 중")}</em></strong>
          <span>${escapeHtml(reconciliationAwareness.headline || reconciliationAwareness.message || "대조 기록 대기")}</span>
          <small>${escapeHtml(reconciliationAwareness.next || "한투 체결과 계좌 잔고를 읽기전용으로 맞춰봅니다.")}</small>
        </div>
        <div>
          <b>${escapeHtml(reconciliationAwareness.check_status === "pass" ? "통과" : reconciliationAwareness.check_status === "block" ? "차단" : "대기")}</b>
          <small>${escapeHtml(reconciliationAwareness.age_label || "시각 대기")}</small>
        </div>
        <button type="button" data-refresh-reconciliation="1">지금 대조</button>
      </div>
    ` : ""}
    ${renderLiveOrderStateMachineCard(orderStateMachine)}
    ${preflight.score != null ? `
      <div class="trade-preflight ${escapeHtml(preflight.tone || "wait")}">
        <div class="trade-preflight-score">
          <small>실전 사전점검</small>
          <strong>${preflightScore.toFixed(1)}점</strong>
          <span>${escapeHtml(preflight.grade || "점검 중")}</span>
        </div>
        <div class="trade-preflight-bars">
          ${preflightItems.map((item) => {
            const score = Number(item.score || 0);
            return `
              <div class="${escapeHtml(item.tone || "wait")}">
                <b>${escapeHtml(item.label || "-")} <em>${score.toFixed(1)}</em></b>
                <i><span style="width:${Math.max(0, Math.min(score, 100)).toFixed(1)}%"></span></i>
                <small>${escapeHtml(item.detail || "-")}</small>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    ` : ""}
    ${recommended.label ? `
      <div class="trade-blocker-next">
        <b>${escapeHtml(recommended.label)}</b>
        <span>${escapeHtml(recommended.detail || "다음 버튼을 확인하세요.")}</span>
        ${recommended.button_id ? `<button type="button" data-pilot-target-button="${escapeHtml(recommended.button_id)}">${escapeHtml(recommended.button_label || "다음 위치 찾기")}</button>` : ""}
      </div>
    ` : ""}
    ${approvalIssue.message ? `
      <div class="trade-blocker-issue">
        <b>승인 토큰 문제</b>
        <span>${escapeHtml(approvalIssue.message)}</span>
        ${approvalIssue.token_masked ? `<code>${escapeHtml(approvalIssue.token_masked)}</code>` : ""}
      </div>
    ` : ""}
    ${workflow.safety_notice ? `
      <div class="trade-blocker-final-lock">
        <b>최종 확인 잠금</b>
        <span>${escapeHtml(workflow.safety_notice)}</span>
        ${workflow.confirm_phrase ? `<code>${escapeHtml(workflow.confirm_phrase)}</code>` : ""}
        ${workflow.confirm_phrase ? `<button type="button" data-copy-confirm-phrase="${escapeHtml(workflow.confirm_phrase)}">문구 복사</button>` : ""}
      </div>
    ` : ""}
    <div class="trade-blocker-mini">
      <div><b>${escapeHtml(market.phase_label || "-")}</b><small>한국장</small></div>
      <div><b>${policy.delegated_live_autonomy_enabled ? "ON" : "OFF"}</b><small>위임</small></div>
      <div><b>${Number(policy.delegated_live_auto_submit_max_cash_pct ?? policy.live_pilot_max_cash_pct ?? 0).toFixed(1)}%</b><small>AI자율</small></div>
      <div><b>${Number(policy.delegated_live_user_approval_above_cash_pct ?? 50).toFixed(1)}%</b><small>승인기준</small></div>
      <div><b>${Number(policy.max_position_pct || 0).toFixed(1)}%</b><small>종목한도</small></div>
      <div><b>${escapeHtml(workflow.stage_label || "-")}</b><small>주문단계</small></div>
    </div>
    <div class="trade-blocker-checks">
      ${checks.slice(0, 8).map((item) => `
        <span class="${escapeHtml(item.status || "wait")}">
          <b>${escapeHtml(item.label || "-")}</b>
          <small>${escapeHtml(item.detail || "-")}</small>
        </span>
      `).join("")}
    </div>
    <small>${escapeHtml(snapshot.safety || "빠른 진단 전용입니다. 실제 주문은 실행하지 않습니다.")}</small>
  `;
}

function renderLiveOrderStateMachineCard(machine = {}) {
  const workflows = Array.isArray(machine.workflows) ? machine.workflows : [];
  const active = machine.active && typeof machine.active === "object" ? machine.active : (workflows[0] || {});
  const stageState = active.stage_state && typeof active.stage_state === "object" ? active.stage_state : {};
  const events = Array.isArray(active.events) ? active.events : [];
  const stateCounts = machine.state_counts && typeof machine.state_counts === "object" ? machine.state_counts : {};
  const stageDefs = [
    ["candidate", "후보"],
    ["approval", "승인"],
    ["dry_submit", "Dry"],
    ["broker_submit", "전송"],
    ["reconciliation", "대조"],
  ];
  const currentStage = String(active.current_stage || "idle").replace(/[^a-z0-9_-]/gi, "-").toLowerCase();
  const activeName = active.name || active.symbol || "진행 중 주문 없음";
  const activeLine = active.symbol
    ? `${activeName} · ${active.side_label || active.side || "-"} ${Number(active.quantity || 0).toLocaleString()}주`
    : "오늘 연결된 실전 후보/승인/전송 흐름이 없습니다.";
  const latestEvents = events.slice(-4).reverse();
  return `
    <div class="trade-order-state-machine ${escapeHtml(currentStage)}">
      <div class="trade-order-state-head">
        <div>
          <strong>실전 주문 타임라인 <em>${escapeHtml(active.current_label || "대기")}</em></strong>
          <span>${escapeHtml(machine.headline || "주문 상태 흐름을 확인하는 중입니다.")}</span>
          <small>${escapeHtml(active.next_action || machine.safety || "후보가 생기면 단계별로 자동 표시됩니다.")}</small>
        </div>
        <div>
          <b>${Number(workflows.length || 0).toLocaleString()}건</b>
          <small>복원된 흐름</small>
        </div>
      </div>
      <div class="trade-order-state-active">
        <b>${escapeHtml(activeLine)}</b>
        <span>${escapeHtml(active.token_masked ? `승인토큰 ${active.token_masked}` : "토큰 없음 또는 대기")}</span>
      </div>
      <div class="trade-order-state-steps">
        ${stageDefs.map(([key, label], index) => {
          const status = String(stageState[key] || "missing").replace(/[^a-z0-9_-]/gi, "-").toLowerCase();
          const event = active.stages && typeof active.stages === "object" ? active.stages[key] || {} : {};
          return `
            <span class="${escapeHtml(status)}">
              <i>${index + 1}</i>
              <b>${escapeHtml(label)}</b>
              <small>${escapeHtml(status === "done" ? "완료" : status === "blocked" ? "차단" : status === "wait" ? "대기" : "없음")}</small>
              ${event.detail ? `<em>${escapeHtml(String(event.detail).slice(0, 80))}</em>` : ""}
            </span>
          `;
        }).join("")}
      </div>
      <div class="trade-order-state-events">
        ${latestEvents.length ? latestEvents.map((event) => `
          <span class="${escapeHtml(String(event.status || "wait").replace(/[^a-z0-9_-]/gi, "-").toLowerCase())}">
            <b>${escapeHtml(event.label || event.stage || "-")}</b>
            <small>${escapeHtml(event.at || "-")}</small>
            <em>${escapeHtml(event.detail || event.raw_status || "-")}</em>
          </span>
        `).join("") : `<span class="empty"><b>기록 없음</b><small>${escapeHtml(machine.date || "-")}</small><em>후보가 만들어지면 이곳에 단계 기록이 쌓입니다.</em></span>`}
      </div>
      <div class="trade-order-state-foot">
        <span>상태분포: ${Object.entries(stateCounts).map(([key, value]) => `${key} ${value}`).join(" · ") || "없음"}</span>
        <button type="button" data-refresh-order-state="1">타임라인 새로고침</button>
      </div>
    </div>
  `;
}

async function loadTradeBlockerSnapshot(silent = true) {
  try {
    const response = await fetch("/api/ops/trade-blockers/quick");
    const snapshot = await response.json();
    if (!response.ok || !snapshot.ok) throw new Error(snapshot.error || "빠른 진단 실패");
    if (!snapshot.order_state_machine || !Array.isArray(snapshot.order_state_machine.workflows)) try {
      const stateResponse = await fetch("/api/ops/live-order-state-machine?limit=5&date=recent");
      const orderState = await stateResponse.json();
      if (stateResponse.ok && orderState.ok) {
        snapshot.order_state_machine = orderState;
      } else {
        snapshot.order_state_machine = {
          ok: false,
          headline: orderState.message || orderState.error || "주문 타임라인 조회 대기",
          workflows: [],
        };
      }
    } catch (stateError) {
      snapshot.order_state_machine = {
        ok: false,
        headline: `주문 타임라인 조회 실패: ${stateError.message}`,
        workflows: [],
      };
    }
    renderTradeBlockerSnapshot(snapshot);
    if (!silent) addLog(`빠른 매매 대기 원인: ${snapshot.headline || "-"}`);
    return snapshot;
  } catch (error) {
    renderTradeBlockerSnapshot({
      state: "ERROR",
      headline: "빠른 진단 실패",
      next_action: error.message,
      checks: [],
      safety: "실제 주문은 실행하지 않았습니다.",
    });
    if (!silent) addLog(`빠른 매매 대기 원인 조회 실패: ${error.message}`);
    return null;
  }
}

async function runLiveReconciliationCheck(silent = false) {
  try {
    const response = await fetch("/api/ops/reconciliation?persist=1&refresh=1");
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.error || result.message || "체결/잔고 대조 실패");
    if (!silent) {
      const summary = result.summary || {};
      addLog(`체결/잔고 대조: ${result.status || "-"} · 차단 ${Number(summary.blockers || 0)}개 · 경고 ${Number(summary.warnings || 0)}개`);
    }
    await loadTradeBlockerSnapshot(true);
    return result;
  } catch (error) {
    if (!silent) addLog(`체결/잔고 대조 실패: ${error.message}`);
    return null;
  }
}

async function loadLiveOrderBlackbox(options = {}) {
  const persist = Boolean(options.persist);
  try {
    const response = await fetch(`/api/ops/live-order-blackbox?limit=8${persist ? "&persist=1" : ""}`);
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || result.message || "블랙박스 조회 실패");
    renderLiveOrderBlackbox(result);
    if (persist) addLog(`실전 주문 블랙박스 스냅샷 저장: ${result.counts?.total || 0}건`);
    return result;
  } catch (error) {
    renderLiveOrderBlackbox({ headline: `실전 주문 블랙박스 조회 실패: ${error.message}`, records: [] });
    if (!options.silent) addLog(`실전 주문 블랙박스 조회 실패: ${error.message}`);
    return null;
  }
}

function renderLivePilotPlan(plan = {}) {
  state.lastLivePilotPlan = plan;
  if (plan.side) state.lastLivePilotSide = String(plan.side).toUpperCase() === "SELL" ? "SELL" : "BUY";
  const checks = Array.isArray(plan.checks) ? plan.checks : [];
  const blocked = checks.filter((item) => item.status === "blocked");
  const warnings = checks.filter((item) => item.status === "warning");
  const brokerReady = Boolean(plan.broker_submit_ready);
  const candidateReady = Boolean(plan.candidate_ready);
  const approvalApproved = plan.latest_approval?.status === "approved";
  const approvalPending = plan.latest_approval?.status === "pending";
  const dryReady = plan.latest_dry_submit?.status === "LIVE_READY_NOT_SUBMITTED";
  const freshness = plan.data_freshness || {};
  const quote = plan.quote || {};
  const liveOrderState = plan.live_order_state || {};
  const operatorGuide = plan.operator_guide || {};
  const planQuantity = Number(plan.quantity || 0);
  const planMode = String(plan.plan_mode || "full").toLowerCase();
  const isQuickPlan = planMode === "quick";
  const perfMs = Number(plan.performance?.elapsed_ms || 0);
  const modeLabel = isQuickPlan ? "빠른 점검" : "전체 검증";
  const modeDetail = isQuickPlan
    ? "화면 반응을 위해 장마감 중 일부 상세 센서를 생략합니다. 실제 후보 생성/주문 전에는 전체 검증을 다시 봅니다."
    : "호가, 분봉, 체결강도, 주문근거까지 더 꼼꼼히 확인한 결과입니다.";
  const confirmPhrase = plan.policy?.live_pilot_confirm_phrase || operatorGuide.confirm_phrase || "1주 파일럿 승인";
  const operatorNextStep = operatorGuide.next_pc_action || {};
  const operatorPcSteps = Array.isArray(operatorGuide.pc_steps) ? operatorGuide.pc_steps : [];
  const operatorTelegramSteps = Array.isArray(operatorGuide.telegram_steps) ? operatorGuide.telegram_steps : [];
  const unlockSteps = Array.isArray(plan.submit_unlock_steps) ? plan.submit_unlock_steps : [];
  const nextUnlock = plan.next_unlock_action || unlockSteps.find((step) => !["done", "ready"].includes(step.status)) || {};
  const nextRequired = plan.next_required_action || {};
  const nextUnlockDueAt = nextUnlock.due_at || nextUnlock.next_event_at || "";
  const nextUnlockMinutes = nextUnlock.minutes_to_due ?? nextUnlock.minutes_to_next ?? "";
  const hasSeparateRequiredAction = Boolean(nextRequired.label && nextRequired.label !== nextUnlock.label);
  const nextRequiredDueAt = nextRequired.due_at || nextRequired.next_event_at || "";
  const nextRequiredMinutes = nextRequired.minutes_to_due ?? nextRequired.minutes_to_next ?? "";
  const regularCheck = checks.find((item) => item.label === "정규장 확인" || item.label === "정규장") || {};
  const freshnessCheck = checks.find((item) => item.label === "데이터 최신성" || item.label === "최종 데이터 최신성") || {};
  const approvalLabel = approvalApproved ? "승인 완료" : approvalPending ? "승인 대기" : "승인 없음";
  const dryLabel = dryReady ? "Dry 통과" : "Dry 대기";
  setText("pilotState", `${modeLabel} · ${brokerReady ? "최종 전송 가능" : candidateReady ? `${warnings.length} 절차 남음` : `${blocked.length} 차단`}`);
  setText("pilotSymbol", `${symbolDisplayName(plan.symbol || state.active, plan)} ${plan.side || "BUY"} ${planQuantity ? `${planQuantity.toLocaleString()}주` : ""}`);
  setText("pilotNotional", `${Number(plan.notional || 0).toLocaleString()}원`);
  setText("pilotTargetDate", plan.target_date || "-");
  setText("pilotCandidateReady", candidateReady ? "준비" : "차단");
  setText("pilotBrokerReady", brokerReady ? "준비" : "잠금");
  if (el("#pilotCandidateReady")) el("#pilotCandidateReady").className = candidateReady ? "up" : "down";
  if (el("#pilotBrokerReady")) el("#pilotBrokerReady").className = brokerReady ? "up" : "down";
  const flowState = [
    ["#pilotFlowCandidate", candidateReady ? "done" : blocked.length ? "blocked" : "active"],
    ["#pilotFlowApprove", approvalApproved ? "done" : approvalPending ? "active" : candidateReady ? "active" : "blocked"],
    ["#pilotFlowDry", dryReady ? "done" : approvalApproved ? "active" : "blocked"],
    ["#pilotFlowSubmit", brokerReady ? "active" : "blocked"],
  ];
  flowState.forEach(([selector, className]) => {
    const node = el(selector);
    if (node) node.className = className;
  });
  const submitButton = el("#pilotLiveSubmit");
  if (submitButton) {
    submitButton.disabled = !brokerReady;
    submitButton.title = brokerReady ? `확인문구 입력 후 실제 브로커로 ${planQuantity.toLocaleString()}주 주문을 전송합니다.` : "승인과 dry-submit을 먼저 통과해야 합니다.";
  }
  const confirmInput = el("#pilotConfirmPhrase");
  if (confirmInput) confirmInput.placeholder = confirmPhrase;
  const safetyNode = el("#pilotSafetySummary");
  if (safetyNode) {
    const freshnessOk = Boolean(freshness.gate_ok);
    const regularOk = regularCheck.status === "ok";
    const rows = [
      {
        label: "데이터",
        state: freshness.state || (freshnessOk ? "최신" : "재조회 필요"),
        detail: freshness.detail || freshnessCheck.detail || "-",
        klass: freshnessOk ? "ok" : "warn",
      },
      {
        label: "시세",
        state: quote.price ? `${formatKrw(quote.price)} · ${quote.source || "-"}` : "대기",
        detail: quote.updated_at ? `갱신 ${formatDateTimeShort(quote.updated_at)}` : "갱신시각 대기",
        klass: quote.price ? "ok" : "warn",
      },
      {
        label: "시장",
        state: regularOk ? "정규장" : "대기",
        detail: regularCheck.detail || "정규장 확인 대기",
        klass: regularOk ? "ok" : "warn",
      },
      {
        label: "승인",
        state: approvalLabel,
        detail: plan.latest_approval?.expires_at ? `만료 ${formatDateTimeShort(plan.latest_approval.expires_at)}` : "승인 토큰 대기",
        klass: approvalApproved ? "ok" : approvalPending ? "warn" : "block",
      },
      {
        label: "Dry-submit",
        state: dryLabel,
        detail: plan.latest_dry_submit?.created_at ? `검증 ${formatDateTimeShort(plan.latest_dry_submit.created_at)}` : "브로커 전송 전 dry 검증 필요",
        klass: dryReady ? "ok" : "block",
      },
    ];
    safetyNode.innerHTML = `
      <div class="pilot-safety-head">
        <strong>최종 전송 안전요약</strong>
        <span class="${brokerReady ? "ok" : "block"}">${brokerReady ? "브로커 전송 가능" : "전송 잠금"}</span>
      </div>
      <div class="pilot-plan-mode ${isQuickPlan ? "quick" : "full"}">
        <b>${escapeHtml(modeLabel)}</b>
        <strong>${perfMs ? `${Number(perfMs).toLocaleString()}ms` : "-"}</strong>
        <small>${escapeHtml(modeDetail)}</small>
      </div>
      <div class="pilot-order-state ${escapeHtml(liveOrderState.tone || liveOrderState.state || "warn")}">
        <b>실제 주문 상태</b>
        <strong>${escapeHtml(liveOrderState.label || (brokerReady ? "전송 가능" : "주문 미전송"))}</strong>
        <small>${escapeHtml(liveOrderState.message || "최종 확인 전까지 브로커 주문은 전송되지 않습니다.")}</small>
        ${liveOrderState.submitted_at ? `<small>최근 전송 ${escapeHtml(formatDateTimeShort(liveOrderState.submitted_at))} · 오늘 ${Number(liveOrderState.submitted_count || 0).toLocaleString()}건</small>` : ""}
      </div>
      ${(operatorPcSteps.length || operatorTelegramSteps.length) ? `
        <div class="pilot-operator-guide">
          <div>
            <b>${escapeHtml(operatorGuide.title || "조작 안내")}</b>
            <strong>현재 할 일: ${escapeHtml(operatorGuide.current || "-")}</strong>
            <small>${escapeHtml(operatorGuide.message || "최종 전송 전까지 실제 주문은 나가지 않습니다.")}</small>
          </div>
          ${operatorNextStep.button ? `
            <div class="pilot-operator-next-button ${escapeHtml(operatorNextStep.status || "ready")}">
              <b>다음에 누를 버튼</b>
              <strong>${escapeHtml(operatorNextStep.button || "-")}</strong>
              <small>${escapeHtml(operatorNextStep.detail || "-")}</small>
              ${operatorNextStep.button_id ? `<button type="button" data-pilot-target-button="${escapeHtml(operatorNextStep.button_id)}">화면에서 버튼 찾기</button>` : ""}
            </div>
          ` : ""}
          ${operatorPcSteps.length ? `
            <div class="pilot-operator-steps">
              ${operatorPcSteps.map((step) => `
                <span class="${escapeHtml(step.status || "wait")} ${step.button_id && step.button_id === operatorNextStep.button_id ? "current" : ""}">
                  <b>${escapeHtml(step.label || "-")}</b>
                  <em>${escapeHtml(pilotStepStatusLabel(step.status))}</em>
                  <small>${escapeHtml(step.button || "-")}</small>
                  <small>${escapeHtml(step.detail || "-")}</small>
                </span>
              `).join("")}
            </div>
          ` : ""}
          ${operatorTelegramSteps.length ? `
            <div class="pilot-telegram-guide">
              <b>텔레그램 명령 순서</b>
              ${operatorTelegramSteps.map((item) => `<code>${escapeHtml(item)}</code>`).join("")}
            </div>
          ` : ""}
        </div>
      ` : ""}
      ${nextUnlock.label ? `
        <div class="pilot-next-action ${escapeHtml(nextUnlock.status || "wait")}">
          <b>다음 행동</b>
          <strong>${escapeHtml(nextUnlock.label || "-")} · ${escapeHtml(nextUnlock.action || "-")}</strong>
          <small>${escapeHtml(nextUnlock.detail || "-")}</small>
          ${nextUnlockDueAt ? `
            <small class="pilot-next-countdown">
              예정 ${escapeHtml(formatDateTimeShort(nextUnlockDueAt))} · 남은 시간
              <em data-countdown-at="${escapeHtml(nextUnlockDueAt)}" data-countdown-minutes="${escapeHtml(String(nextUnlockMinutes ?? ""))}">${escapeHtml(formatEventCountdown(nextUnlockDueAt, nextUnlockMinutes))}</em>
            </small>
          ` : ""}
          ${hasSeparateRequiredAction ? `
            <div class="pilot-action-split">
              <div class="wait">
                <b>자동 대기</b>
                <span>${escapeHtml(nextUnlock.label || "-")} · ${escapeHtml(pilotStepStatusLabel(nextUnlock.status))}</span>
                <small>${escapeHtml(nextUnlockDueAt ? formatEventCountdown(nextUnlockDueAt, nextUnlockMinutes) : nextUnlock.detail || "-")}</small>
              </div>
              <div class="required">
                <b>사용자 조치</b>
                <span>${escapeHtml(nextRequired.label || "-")} · ${escapeHtml(pilotStepStatusLabel(nextRequired.status))}</span>
                <small>${escapeHtml(nextRequired.action || "-")}</small>
                ${nextRequiredDueAt ? `<small>${escapeHtml(formatDateTimeShort(nextRequiredDueAt))} · ${escapeHtml(formatEventCountdown(nextRequiredDueAt, nextRequiredMinutes))}</small>` : ""}
              </div>
            </div>
            <small class="pilot-next-required">지금은 자동으로 기다릴 일과 사용자가 풀어야 할 잠금이 분리되어 있습니다.</small>
          ` : ""}
        </div>
      ` : ""}
      <div class="pilot-safety-grid">
        ${rows.map((row) => `
          <div class="${row.klass}">
            <b>${escapeHtml(row.label)}</b>
            <span>${escapeHtml(row.state)}</span>
            <small>${escapeHtml(row.detail)}</small>
          </div>
        `).join("")}
      </div>
      ${unlockSteps.length ? `
        <div class="pilot-unlock-steps">
          <strong>잠금 해제 순서</strong>
          ${unlockSteps.map((step, index) => `
            <div class="${escapeHtml(step.status || "wait")}">
              <b>${index + 1}</b>
              <span>${escapeHtml(step.label || "-")}</span>
              <em>${escapeHtml(pilotStepStatusLabel(step.status))}</em>
              <small>${escapeHtml(step.detail || "-")} · ${escapeHtml(step.action || "-")}</small>
            </div>
          `).join("")}
        </div>
      ` : ""}
    `;
  }
  const node = el("#pilotCheckRows");
  if (!node) return;
  const selectionRow = plan.selection_reason
    ? [{ label: "AI 선별 기준", status: "ok", detail: plan.selection_reason }]
    : [];
  const important = [
    ...selectionRow,
    ...checks.filter((item) => item.status === "blocked"),
    ...checks.filter((item) => item.status === "warning"),
    ...checks.filter((item) => item.status === "ok"),
  ].slice(0, 8);
  node.innerHTML = important.length
    ? important.map((item) => {
      const klass = item.status === "ok" ? "up" : item.status === "warning" ? "flat" : "down";
      return `<div class="ops-item">
        <strong>${escapeHtml(item.label || "-")}</strong>
        <span class="${klass}">${escapeHtml(pilotStepStatusLabel(item.status))}</span>
        <small>${escapeHtml(item.detail || "-")}</small>
      </div>`;
    }).join("")
    : `<div class="ops-item"><strong>파일럿 점검 대기</strong><small>AI가 고른 실전 파일럿 후보의 가능 여부를 확인합니다.</small></div>`;
}

async function loadLivePilotPlan(silent = false, side = "", options = {}) {
  if (silent && !options.full && state.livePilotPlanLoading) return state.lastLivePilotPlan;
  state.livePilotPlanLoading = true;
  try {
    const normalizedSide = String(side || state.lastLivePilotSide || state.lastLivePilotPlan?.side || "BUY").toUpperCase() === "SELL" ? "SELL" : "BUY";
    state.lastLivePilotSide = normalizedSide;
    const full = Boolean(options.full);
    const params = new URLSearchParams({ symbol: "AI", side: normalizedSide });
    if (full) {
      params.set("detail", "full");
      params.set("quick", "0");
    }
    const response = await fetch(`/api/ops/live-pilot/plan?${params.toString()}`);
    const plan = await response.json();
    state.livePilotPlanLoadedAt = Date.now();
    renderLivePilotPlan(plan);
    if (plan.candidate_decision_preview) {
      renderLiveCandidateDecision(plan.candidate_decision_preview);
    } else {
      loadLiveCandidateDecisions(true).catch(() => {});
    }
    if (!silent) addLog(`AI ${normalizedSide === "SELL" ? "매도" : "매수"} 파일럿 ${full ? "전체 검증" : "빠른 점검"}: ${symbolDisplayName(plan.symbol || state.active, plan)} ${Number(plan.quantity || 0).toLocaleString()}주 · 후보 ${plan.candidate_ready ? "준비" : "차단"} · ${plan.performance?.elapsed_ms ? `${Number(plan.performance.elapsed_ms).toLocaleString()}ms` : "시간 미측정"}`);
    return plan;
  } catch (error) {
    setText("pilotState", "조회 실패");
    if (!silent) addLog(`AI 파일럿 계획 조회 실패: ${error.message}`);
    return null;
  } finally {
    state.livePilotPlanLoading = false;
  }
}

async function createLivePilotCandidate(side = "BUY") {
  const normalizedSide = String(side || "BUY").toUpperCase() === "SELL" ? "SELL" : "BUY";
  state.lastLivePilotSide = normalizedSide;
  try {
    const response = await fetch("/api/ops/live-pilot/candidate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: "AI", side: normalizedSide }),
    });
    const result = await response.json();
    if (result.plan) renderLivePilotPlan(result.plan);
    if (result.candidate_decision_report) renderLiveCandidateDecision(result.candidate_decision_report);
    if (!response.ok || !result.ok) {
      const blocked = result.plan?.checks?.filter((item) => item.status === "blocked") || [];
      addLog(`AI ${normalizedSide === "SELL" ? "매도" : "매수"} 파일럿 후보 차단: ${result.message || result.error || "점검 필요"}${blocked.length ? ` · ${blocked[0].label}` : ""}`);
      return result;
    }
    state.lastApprovalToken = result.ticket?.approval_token || state.lastApprovalToken;
    addLog(`AI ${normalizedSide === "SELL" ? "매도" : "매수"} 파일럿 후보 생성: ${symbolDisplayName(result.ticket?.symbol || state.active, result.ticket)} ${Number(result.ticket?.quantity || result.plan?.quantity || 0).toLocaleString()}주 / 승인토큰 ${result.ticket?.approval_token || "-"}`);
    loadLiveCandidateDecisions(true).catch(() => {});
    await loadOpsStatus();
    await loadAlerts();
    return result;
  } catch (error) {
    addLog(`AI ${normalizedSide === "SELL" ? "매도" : "매수"} 파일럿 후보 생성 실패: ${error.message}`);
    return null;
  }
}

async function createOpsPaperBuy() {
  try {
    const result = await postOps("/api/ops/paper/order", { symbol: state.active, side: "BUY", quantity: Number(el("#quantity")?.value || 1), source: "ui-ops" });
    addLog(`Paper 티켓: ${symbolDisplayName(result.ticket?.symbol || state.active, result.ticket)} ${result.ticket?.status || "-"}`);
    await loadAlerts();
  } catch (error) {
    addLog(`Paper 티켓 실패: ${error.message}`);
  }
}

async function createOpsLiveCandidate() {
  try {
    const result = await postOps("/api/ops/live-candidate", { symbol: state.active, side: "BUY", quantity: Number(el("#quantity")?.value || 1), source: "ui-ops", memo: "사용자/AI 검토용 실전 후보" });
    state.lastApprovalToken = result.ticket?.approval_token || state.lastApprovalToken;
    addLog(`실전 후보 생성: ${symbolDisplayName(result.ticket?.symbol || state.active, result.ticket)} / ${result.ticket?.status || "-"}`);
    await loadAlerts();
  } catch (error) {
    addLog(`실전 후보 실패: ${error.message}`);
  }
}

async function approveLatestOps() {
  if (!state.lastApprovalToken) return addLog("승인할 토큰이 없습니다. 먼저 실전 후보를 생성하세요.");
  try {
    const result = await postOps("/api/ops/approvals/resolve", { token: state.lastApprovalToken, approved: true, memo: "UI에서 최근 승인 허용" });
    addLog(`승인 처리: ${result.approval?.token || state.lastApprovalToken}`);
    await loadAlerts();
  } catch (error) {
    addLog(`승인 처리 실패: ${error.message}`);
  }
}

async function drySubmitOps() {
  if (!state.lastApprovalToken) return addLog("dry-submit할 승인 토큰이 없습니다.");
  try {
    const result = await postOps("/api/ops/live/dry-submit", { token: state.lastApprovalToken });
    addLog(`Dry-submit: ${result.result?.status || "-"}. 통과하면 확인문구 입력 후 최종 전송 버튼이 활성화됩니다.`);
    await loadAlerts();
  } catch (error) {
    addLog(`Dry-submit 실패: ${error.message}`);
  }
}

async function liveSubmitPilotOps() {
  if (!state.lastApprovalToken) return addLog("최종 전송할 승인 토큰이 없습니다. 먼저 파일럿 후보 생성과 승인을 진행하세요.");
  const confirmPhrase = (el("#pilotConfirmPhrase")?.value || "").trim();
  const plan = state.lastLivePilotPlan || {};
  const expectedPhrase = plan.policy?.live_pilot_confirm_phrase || plan.operator_guide?.confirm_phrase || "1주 파일럿 승인";
  if (confirmPhrase !== expectedPhrase) {
    return addLog(`최종 실주문 전송 전 확인문구를 정확히 입력하세요: ${expectedPhrase}`);
  }
  const planQuantity = Number(plan.quantity || 0);
  const message = `${symbolDisplayName(plan.symbol || state.active, plan)} ${plan.side || "BUY"} ${planQuantity.toLocaleString()}주를 실제 한투 계좌로 전송합니다.\n예상 주문금액: ${Number(plan.notional || 0).toLocaleString()}원\n계속할까요?`;
  if (!window.confirm(message)) {
    return addLog("최종 실주문 전송을 사용자가 취소했습니다.");
  }
  try {
    const result = await postOps("/api/ops/live/submit", {
      token: state.lastApprovalToken,
      confirm_phrase: confirmPhrase,
      order_type: "limit",
    });
    addLog(`최종 실주문: ${result.result?.status || "-"} / ${result.result?.message || ""}`);
    if (result.result?.plan) renderLivePilotPlan(result.result.plan);
    await loadOpsStatus();
    await loadAlerts();
    return result;
  } catch (error) {
    addLog(`최종 실주문 차단: ${error.message}`);
    await loadLivePilotPlan(true);
    return null;
  }
}

function buildOpsPolicyPayload(extra = {}) {
  return {
    max_order_amount: Number(el("#opsPolicyMaxOrder")?.value || 2000000),
    max_daily_orders: Number(el("#opsPolicyMaxDailyOrders")?.value || 20),
    max_position_pct: Number(el("#opsPolicyMaxPosition")?.value || 10),
    max_daily_loss_pct: Number(el("#opsPolicyDailyLoss")?.value || 2),
    live_pilot_sizing_mode: "cash_pct",
    live_pilot_max_quantity: Number(el("#opsPolicyPilotMaxQty")?.value || 1),
    live_pilot_max_cash_pct: Number(el("#opsPolicyPilotCashPct")?.value || 10),
    live_pilot_dynamic_sizing_enabled: true,
    live_pilot_dynamic_max_cash_pct: Number(el("#opsPolicyDynamicMaxCashPct")?.value || el("#opsPolicyPilotCashPct")?.value || 50),
    delegated_live_auto_submit_max_cash_pct: Number(el("#opsPolicyAutoCashPct")?.value || 30),
    delegated_live_user_approval_above_cash_pct: Number(el("#opsPolicyApprovalCashPct")?.value || 50),
    live_pilot_max_notional: Number(el("#opsPolicyMaxOrder")?.value || 2000000),
    live_pilot_enabled: Boolean(el("#opsPolicyLivePilot")?.checked),
    live_execution_enabled: Boolean(el("#opsPolicyLiveExecution")?.checked),
    memo: "UI에서 자동매매 운영 정책 저장",
    ...extra,
  };
}

async function saveOpsPolicy() {
  try {
    const payload = buildOpsPolicyPayload();
    updateOpsCapitalRiskBadge(payload);
    if (Math.max(payload.live_pilot_max_cash_pct, payload.live_pilot_dynamic_max_cash_pct, payload.delegated_live_auto_submit_max_cash_pct, payload.delegated_live_user_approval_above_cash_pct) >= 80) {
      addLog("자금 운용 비중이 80% 이상입니다. 고위험 설정으로 저장하지만 자동 제출은 승인 게이트를 거칩니다.");
    }
    const result = await postOps("/api/ops/autotrade/policy", payload);
    addLog(`자동매매 정책 저장: 준비도 ${result.readiness?.score ?? "-"}점`);
    await loadAutopilotStatus();
    return result;
  } catch (error) {
    addLog(`자동매매 정책 저장 실패: ${error.message}`);
    throw error;
  }
}

async function applyActive50Policy() {
  const button = el("#opsActive50Mode");
  const hint = el("#opsActive50Hint");
  const maxQty = el("#opsPolicyPilotMaxQty");
  const cashPct = el("#opsPolicyPilotCashPct");
  const autoCashPct = el("#opsPolicyAutoCashPct");
  const approvalCashPct = el("#opsPolicyApprovalCashPct");
  const dynamicMaxCashPct = el("#opsPolicyDynamicMaxCashPct");
  const maxPosition = el("#opsPolicyMaxPosition");
  const maxOrder = el("#opsPolicyMaxOrder");
  if (button) button.disabled = true;
  if (hint) {
    hint.textContent = "50% 적극모드 정책을 저장하는 중입니다. 위임 자동주문은 켜지 않고 실제 주문도 전송하지 않습니다.";
    hint.className = "ops-policy-hint active";
  }
  if (maxQty) maxQty.value = "10000";
  if (cashPct) cashPct.value = "50";
  if (autoCashPct) autoCashPct.value = "30";
  if (approvalCashPct) approvalCashPct.value = "50";
  if (dynamicMaxCashPct) dynamicMaxCashPct.value = "50";
  if (maxPosition) maxPosition.value = "50";
  if (maxOrder && Number(maxOrder.value || 0) < 300000) maxOrder.value = "300000";
  if (el("#opsPolicyLivePilot")) el("#opsPolicyLivePilot").checked = true;
  updateOpsCapitalRiskBadge(buildOpsPolicyPayload());
  try {
    const payload = buildOpsPolicyPayload({
      live_pilot_sizing_mode: "cash_pct",
      live_pilot_max_quantity: 10000,
      live_pilot_max_cash_pct: 50,
      live_pilot_dynamic_sizing_enabled: true,
      live_pilot_dynamic_max_cash_pct: 50,
      delegated_live_auto_submit_max_cash_pct: 30,
      delegated_live_user_approval_above_cash_pct: 50,
      max_position_pct: 50,
      delegated_live_autonomy_enabled: false,
      memo: "UI에서 오늘 50% 적극모드 저장: 후보 수량 계산만 변경, 위임 자동주문은 별도 시작 필요",
    });
    await postOps("/api/ops/autotrade/policy", payload);
    await loadAutopilotStatus();
    const plan = await loadLivePilotPlan(false, "BUY");
    const quantity = Number(plan?.quantity || 0);
    const notional = Number(plan?.notional || 0);
    if (hint) {
      hint.textContent = `50% 적극모드 저장 완료. 현재 후보 기준 ${quantity.toLocaleString()}주, 예상 ${notional.toLocaleString()}원까지 계산됐고 위임 자동주문/실제 주문은 아직 미전송입니다.`;
      hint.className = "ops-policy-hint active success";
    }
    addLog("오늘 50% 적극모드 적용: 후보 수량은 주문가능 현금의 50% 이내에서 자동 계산합니다. 위임 자동주문은 꺼두었고 실제 주문은 전송되지 않았습니다.");
  } catch (error) {
    if (hint) {
      hint.textContent = `50% 적극모드 적용 실패: ${error.message}`;
      hint.className = "ops-policy-hint active error";
    }
    addLog(`오늘 50% 적극모드 적용 실패: ${error.message}`);
  } finally {
    if (button) button.disabled = false;
  }
}

async function emergencyStopOps() {
  try {
    const result = await postOps("/api/ops/emergency-stop", { memo: "UI 긴급정지" });
    addLog(result.message || "긴급정지 완료");
    await loadAutopilotStatus();
    await loadAgentDaemon();
  } catch (error) {
    addLog(`긴급정지 실패: ${error.message}`);
  }
}

async function startAutoTradeOps() {
  try {
    const result = await postOps("/api/ops/autotrade/start", { memo: "UI 자동매매 시작" });
    addLog(result.message || "자동매매 시작 완료");
    await loadAutopilotStatus();
    await loadAgentDaemon();
  } catch (error) {
    addLog(`자동매매 시작 실패: ${error.message}`);
  }
}

async function stopAutoTradeOps() {
  try {
    const result = await postOps("/api/ops/autotrade/stop", { memo: "UI 자동매매 멈춤" });
    addLog(result.message || "자동매매 멈춤 완료");
    await loadAutopilotStatus();
    await loadAgentDaemon();
  } catch (error) {
    addLog(`자동매매 멈춤 실패: ${error.message}`);
  }
}

async function resumeOps() {
  try {
    const result = await postOps("/api/ops/resume", { memo: "UI 재개" });
    addLog(result.message || "긴급정지 해제");
    await loadAutopilotStatus();
  } catch (error) {
    addLog(`재개 실패: ${error.message}`);
  }
}

async function queueOpsTelegram() {
  try {
    const top = state.lastOpsStatus?.paper || {};
    const text = `[운영 게이트 보고]\nPaper 평가금 ${money(top.equity || 0)} / 손익 ${pct(top.total_pnl_pct || 0)}\n실전 주문: 잠금\n승인 대기: ${state.lastOpsStatus?.approvals?.pending || 0}`;
    const result = await postOps("/api/ops/telegram/queue", { text, message_type: "ops_report", source: "ui-ops" });
    addLog(`텔레그램 outbox 등록: ${result.record?.id || "-"}`);
  } catch (error) {
    addLog(`텔레그램 큐 실패: ${error.message}`);
  }
}

function renderPortfolioTargets(result = {}) {
  const node = el("#opsTargetRows");
  if (!node) return;
  const summary = result.summary || {};
  const targets = Array.isArray(result.targets) ? result.targets : [];
  setText("opsTargetState", `${summary.ready_count || 0}/${summary.candidate_count || 0} 통과`);
  node.innerHTML = targets.length
    ? targets.map((row) => {
      const blockers = Array.isArray(row.blockers) ? row.blockers : [];
      const klass = row.ready ? "up" : "down";
      const detail = row.ready
        ? `수량 ${row.quantity} · ${Number(row.notional || 0).toLocaleString()}원 · 비중 ${row.target_pct_of_paper}%`
        : blockers.slice(0, 2).map((item) => item.detail || item.name).join(" / ") || "차단 사유 확인";
      return `<div class="ops-item">
        <strong>${escapeHtml(symbolDisplayName(row.symbol, row))}</strong>
        <span class="${klass}">${row.ready ? "준비" : "차단"}</span>
        <small>점수 ${row.score ?? "-"} · 게이트 ${escapeHtml(koreanStatusText(row.gate || "-"))} · ${detail}</small>
      </div>`;
    }).join("")
    : `<div class="ops-item"><strong>목표 계산 대기</strong><small>AI 후보 파이프라인을 읽어 목표 수량을 계산합니다.</small></div>`;
}

async function loadPortfolioTargets() {
  try {
    const response = await fetch("/api/ops/portfolio-targets/preview?limit=6");
    const result = await response.json();
    renderPortfolioTargets(result);
    return result;
  } catch (error) {
    setText("opsTargetState", "계산 실패");
    addLog(`목표 포트폴리오 계산 실패: ${error.message}`);
    return null;
  }
}

async function applyPaperTargets() {
  try {
    const result = await postOps("/api/ops/portfolio-targets/paper", { limit: 5, source: "ui-portfolio-target-planner" });
    addLog(`목표 포트폴리오 Paper 적용: ${result.applied_count || 0}건`);
    renderPortfolioTargets(result.preview || {});
    await loadPipeline();
    await loadAlerts();
  } catch (error) {
    addLog(`목표 포트폴리오 적용 실패: ${error.message}`);
  }
}

function renderCompetitiveAudit(audit = {}) {
  const node = el("#competitiveRows");
  if (!node) return;
  setText("competitiveScore", `${audit.score ?? "-"}점`);
  const auditBadges = [
    audit.cached ? "캐시 즉시 표시" : (audit.fast_mode ? "빠른 비교" : "전체 계산"),
    audit.cache_age_seconds != null ? `${audit.cache_age_seconds}초 전` : "",
  ].filter(Boolean);
  const scoreEntries = audit.user_scorecard && typeof audit.user_scorecard === "object"
    ? Object.entries(audit.user_scorecard)
    : [];
  const gapCards = Array.isArray(audit.user_gap_cards) ? audit.user_gap_cards : [];
  const nextActions = Array.isArray(audit.next_user_actions) ? audit.next_user_actions : [];
  const capabilities = Array.isArray(audit.capabilities) ? audit.capabilities : [];
  const scoreHtml = scoreEntries.length
    ? `<div class="competitive-scorecard">${scoreEntries.map(([label, value]) => `
      <div>
        <strong>${productHtml(value)}점</strong>
        <small>${productHtml(label)}</small>
      </div>`).join("")}</div>`
    : "";
  const gapHtml = gapCards.length
    ? `<div class="competitive-section-title">사용자 관점 반영 과제</div>${gapCards.map((item) => `
      <div class="competitive-gap-card">
        <div class="competitive-gap-top">
          <strong>${productHtml(item.title || "-")}</strong>
          <span>${productHtml(item.priority || "보통")}</span>
        </div>
        <small>${productHtml(item.competitor || "비교 기준")}</small>
        <p>${productHtml(item.ours || "-")}</p>
        <b>부족한 점</b>
        <p>${productHtml(item.gap || "-")}</p>
        <b>반영 방향</b>
        <p>${productHtml(item.action || "-")}</p>
        <em>${productHtml(item.impact || "")}</em>
      </div>`).join("")}`
    : "";
  const actionHtml = nextActions.length
    ? `<div class="competitive-section-title">다음에 누를 것</div>${nextActions.map((item, index) => `
      <div class="competitive-action-card">
        <b>${index + 1}</b>
        <div>
          <strong>${productHtml(item.label || "-")}</strong>
          <span>${productHtml(item.button || "-")}</span>
          <small>${productHtml(item.why || "")}</small>
          ${item.button_id ? `<button type="button" class="competitive-action-go" data-competitive-page="${escapeHtml(item.page || "aiTrader")}" data-competitive-button="${escapeHtml(item.button_id)}">바로 찾아가기</button>` : ""}
        </div>
      </div>`).join("")}`
    : "";
  const capabilitiesHtml = capabilities.length
    ? capabilities.map((item) => {
      const klass = String(item.status || "").includes("반영") ? "up" : "flat";
      return `<div class="ops-item">
        <strong>${productHtml(item.source || "-")}</strong>
        <span class="${klass}">${productHtml(item.status || "-")}</span>
        <small>${productHtml(item.ours || item.lesson || "-")}</small>
      </div>`;
    }).join("")
    : `<div class="ops-item"><strong>완성도 점검 대기</strong><small>전략 검증, 리스크, 실행, 기록 기능을 자체 기준으로 점검합니다.</small></div>`;
  node.innerHTML = `
    <div class="competitive-audit-head">
      <strong>${productHtml(audit.headline || "코덱스스톡 기능 완성도를 점검합니다.")}</strong>
      <span>${productHtml(audit.safety || "비교 감사는 개발 우선순위와 paper 운용 개선용입니다.")}</span>
      <div class="competitive-audit-meta">
        ${auditBadges.map((item) => `<b>${productHtml(item)}</b>`).join("")}
        <small>${productHtml(audit.cache_note || audit.generated_at || "")}</small>
      </div>
    </div>
    ${scoreHtml}
    ${gapHtml}
    ${actionHtml}
    <div class="competitive-section-title">구현 상태</div>
    ${capabilitiesHtml}
  `;
}

function setCompetitiveAuditBusy(isBusy, fullDepth = false) {
  const standardButton = el("#runCompetitiveAudit");
  const fullButton = el("#runCompetitiveAuditFull");
  if (standardButton) {
    standardButton.disabled = Boolean(isBusy);
    standardButton.textContent = isBusy && !fullDepth ? "표준 감사 중" : "표준 감사 실행";
  }
  if (fullButton) {
    fullButton.disabled = Boolean(isBusy || state.competitiveAuditJobRunning);
    fullButton.textContent = state.competitiveAuditJobRunning ? "정밀 감사 진행 중" : isBusy && fullDepth ? "정밀 감사 시작 중" : "전체 정밀 감사";
  }
}

function renderCompetitiveAuditJob(job = {}) {
  state.competitiveAuditJobRunning = Boolean(job.running);
  setCompetitiveAuditBusy(false);
  const audit = job.audit && typeof job.audit === "object" ? job.audit : null;
  if (audit && !job.running) {
    renderCompetitiveAudit(audit);
    if (audit.target_preview) renderPortfolioTargets(audit.target_preview);
    if (audit.live_pilot_plan) renderLivePilotPlan(audit.live_pilot_plan);
    addLog(job.message || "전체 정밀 비교 감사가 완료됐습니다.");
    return;
  }
  const node = el("#competitiveRows");
  if (!node) return;
  setText("competitiveScore", job.running ? "정밀 감사 중" : "정밀 감사 대기");
  node.innerHTML = `
    <div class="competitive-audit-head">
      <strong>${escapeHtml(job.message || "전체 정밀 비교 감사를 백그라운드로 실행 중입니다.")}</strong>
      <span>화면은 계속 사용할 수 있습니다. 완료되면 이 비교판이 자동으로 갱신됩니다.</span>
      <div class="competitive-audit-meta">
        <b>${job.running ? "백그라운드 실행 중" : "대기"}</b>
        <small>${escapeHtml(job.started_at || "")}</small>
      </div>
    </div>
  `;
}

async function loadCompetitiveAuditJob() {
  try {
    const response = await fetch("/api/agent/competitive-audit/job");
    const job = await response.json();
    renderCompetitiveAuditJob(job);
    if (!job.running && state.competitiveAuditJobTimer) {
      clearInterval(state.competitiveAuditJobTimer);
      state.competitiveAuditJobTimer = null;
    }
    return job;
  } catch (error) {
    addLog(`정밀 비교 감사 상태 확인 실패: ${error.message}`);
    return null;
  }
}

function startCompetitiveAuditJobPolling() {
  if (state.competitiveAuditJobTimer) clearInterval(state.competitiveAuditJobTimer);
  state.competitiveAuditJobTimer = setInterval(loadCompetitiveAuditJob, 3000);
}

async function loadCompetitiveAudit(run = false, options = {}) {
  const depth = options.depth || (run ? "standard" : "");
  const fullDepth = depth === "full";
  if (run && state.competitiveAuditBusy) {
    addLog("이미 비교 감사가 실행 중입니다. 현재 계산이 끝난 뒤 다시 눌러주세요.");
    return null;
  }
  if (run) {
    state.competitiveAuditBusy = true;
    setCompetitiveAuditBusy(true, fullDepth);
  }
  const node = el("#competitiveRows");
  if (node) {
    setText("competitiveScore", run ? (fullDepth ? "정밀 계산 중" : "표준 계산 중") : "불러오는 중");
    node.innerHTML = `
      <div class="competitive-audit-head">
        <strong>${run ? (fullDepth ? "전체 정밀 기능 점검을 실행하고 있습니다." : "표준 기능 점검을 빠르게 실행하고 있습니다.") : "기능 완성도 점검 결과를 불러오는 중입니다."}</strong>
        <span>${fullDepth ? "목표 포트폴리오, 실전 파일럿, 리스크 상태까지 함께 계산해서 오래 걸릴 수 있습니다." : "표준 감사는 무거운 계산을 생략하고 사용자 관점 격차와 다음 행동을 빠르게 갱신합니다."}</span>
        <small>주문은 실행하지 않고 비교/개발 우선순위만 계산합니다.</small>
      </div>
    `;
  }
  try {
    const response = run
      ? await fetch("/api/agent/competitive-audit/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ depth: fullDepth ? "full" : "standard", async: fullDepth }) })
      : await fetch("/api/agent/competitive-audit");
    const result = await response.json();
    if (fullDepth && run && !result.audit) {
      renderCompetitiveAuditJob(result);
      addLog(result.message || "전체 정밀 비교 감사를 백그라운드로 시작했습니다.");
      startCompetitiveAuditJobPolling();
      return null;
    }
    const audit = result.audit || result;
    renderCompetitiveAudit(audit);
    if (audit.target_preview) renderPortfolioTargets(audit.target_preview);
    if (audit.live_pilot_plan) renderLivePilotPlan(audit.live_pilot_plan);
    if (run) {
      addLog(`기능 완성도 점검: ${audit.score ?? "-"}점`);
      if (result.message) addLog(result.message);
      if (fullDepth) {
        await loadOpsStatus();
      } else {
        loadOpsStatus().catch((error) => addLog(`운영 상태 백그라운드 갱신 실패: ${error.message}`));
      }
    }
    return audit;
  } catch (error) {
    setText("competitiveScore", "실패");
    addLog(`기능 완성도 점검 실패: ${error.message}`);
    return null;
  } finally {
    if (run) {
      state.competitiveAuditBusy = false;
      setCompetitiveAuditBusy(false);
    }
  }
}

function renderAlerts(center = {}) {
  const summary = center.summary || {};
  setText("alertsState", center.safety || "실전 주문 잠금");
  const summaryNode = el("#alertsSummary");
  if (summaryNode) {
    summaryNode.innerHTML = `
      <div><span>${summary.total || 0}</span><small>전체 알림</small></div>
      <div><span>${summary.warning || 0}</span><small>주의</small></div>
      <div><span>${summary.opportunity || 0}</span><small>기회</small></div>
      <div><span>${summary.info || 0}</span><small>정보</small></div>
      <div><span>${summary.paper_rehearsal_count || 0}/${summary.paper_rehearsal_warning || 0}</span><small>리허설/경고</small></div>
      <div><span>${escapeHtml(realExecutionLabel(summary.real_execution || "BLOCKED"))}</span><small>실전 주문</small></div>
    `;
  }
  const list = el("#alertsList");
  const alerts = Array.isArray(center.alerts) ? center.alerts : [];
  if (!list) return;
  list.innerHTML = alerts.length
    ? alerts.map((item) => `
      <div class="alert-item ${item.priority || "info"}">
        <div>
          <strong>${item.title || "-"}</strong>
          <span>${escapeHtml(item.category || "-")} · ${escapeHtml(item.priority || "info")}${item.symbol ? ` · ${escapeHtml(symbolDisplayName(item.symbol, item))}` : ""}</span>
        </div>
        <p>${item.message || "-"}</p>
        <small>${item.action || ""}</small>
      </div>
    `).join("")
    : `<div class="alert-item info"><strong>알림 없음</strong><p>AI가 시장/파이프라인/운영 장부를 계속 감시 중입니다.</p></div>`;
}

async function loadAlerts() {
  try {
    const response = await fetch("/api/agent/alerts");
    const center = await response.json();
    renderAlerts(center);
  } catch (error) {
    setText("alertsState", "조회 실패");
    addLog(`AI 알림 조회 실패: ${error.message}`);
  }
}

async function queueAlertDigest() {
  try {
    const response = await fetch("/api/agent/alerts/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "ui-alert-center" }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "알림 큐 실패");
    renderAlerts(result.alerts || {});
    addLog(`AI 알림 요약 outbox 등록: ${result.record?.id || "-"}`);
    await loadOpsStatus();
    await loadDispatchCenter();
  } catch (error) {
    addLog(`AI 알림 요약 큐 실패: ${error.message}`);
  }
}

function renderDispatchRows(selector, rows = [], emptyText = "기록 없음") {
  const node = el(selector);
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 10).map((row) => {
      const id = row.id || row.outbox_id || "-";
      const status = row.status || row.message_type || "-";
      const detail = row.message || row.text || row.created_at || "";
      const klass = status === "sent" ? "sent" : status === "failed" ? "failed" : status === "dry_run" ? "dry" : "queued";
      return `
        <div class="dispatch-item ${klass}">
          <strong>${id}</strong>
          <span>${status}</span>
          <small>${String(detail).slice(0, 180)}</small>
        </div>
      `;
    }).join("")
    : `<div class="dispatch-item queued"><strong>${emptyText}</strong><small>보고 큐가 처리되면 여기에 표시됩니다.</small></div>`;
}

function renderDispatchPolicy(center = {}) {
  const node = el("#dispatchPolicyRows");
  if (!node) return;
  const policy = center.policy || {};
  const stats = center.policy_stats || {};
  const summary = center.summary || {};
  const dispatcher = center.dispatcher || {};
  const intervals = policy.min_interval_minutes_by_type || {};
  const softLimits = policy.pending_soft_limit_by_type || {};
  const overflows = Array.isArray(summary.soft_overflows) ? summary.soft_overflows : [];
  const intervalText = Object.entries(intervals)
    .filter(([, value]) => Number(value) > 0)
    .map(([key, value]) => `${key} ${value}분`)
    .join(" · ") || "제한 없음";
  const softText = Object.entries(softLimits)
    .map(([key, value]) => `${key} ${value}건`)
    .join(" · ") || "기본값";
  const overflowText = overflows.length
    ? overflows.map((row) => `${row.message_type} ${row.count}/${row.limit}`).join(" · ")
    : "초과 없음";
  node.innerHTML = `
    <div class="dispatch-policy ${policy.enabled ? "on" : "off"}">
      <b>보고 정책</b>
      <span>${policy.enabled ? "활성" : "비활성"} · 자동발송 ${policy.auto_dispatch ? "켜짐" : "꺼짐"}</span>
      <small>${escapeHtml(koreanStatusText(policy.safety || "실제 주문은 잠금입니다."))}</small>
    </div>
    <div class="dispatch-policy ${dispatcher.running && dispatcher.thread_alive ? "on" : "warn"}">
      <b>자동발송 루프</b>
      <span>${dispatcher.running && dispatcher.thread_alive ? "실행 중" : "대기"} · 최근대상 ${dispatcher.eligible_recent || 0}/${dispatcher.pending_total || 0}건</span>
      <small>${dispatcher.last_tick ? `마지막 ${dispatcher.last_tick} · 처리 ${dispatcher.last_processed || 0}건` : dispatcher.safety || "최근 보고만 천천히 발송합니다."}</small>
    </div>
    <div class="dispatch-policy">
      <b>중복 차단</b>
      <span>${policy.dedupe_enabled ? "켜짐" : "꺼짐"} · ${policy.dedupe_window_minutes || 0}분 창</span>
      <small>최근 보류 ${stats.recent_skips || 0}건 · ${JSON.stringify(stats.by_status || {})}</small>
    </div>
    <div class="dispatch-policy">
      <b>빈도 제한</b>
      <span>${policy.rate_limit_enabled ? "켜짐" : "꺼짐"}</span>
      <small>${intervalText}</small>
    </div>
    <div class="dispatch-policy ${overflows.length ? "warn" : ""}">
      <b>대기열 한도</b>
      <span>${overflowText}</span>
      <small>${softText}</small>
    </div>
  `;
}

async function loadDispatchCenter() {
  try {
    const response = await fetch("/api/telegram/dispatch-center");
    const center = await response.json();
    const summary = center.summary || {};
    const status = center.telegram_status || {};
    setText("dispatchState", status.enabled ? status.dry_run ? "드라이런" : "활성" : "비활성");
    setText("dispatchSafety", center.safety || "보고 발송 상태를 확인합니다.");
    const summaryNode = el("#dispatchSummary");
    if (summaryNode) {
      summaryNode.innerHTML = `
        <div><span>${summary.pending || 0}</span><small>발송 대기</small></div>
        <div><span>${summary.sent || 0}</span><small>전송 완료</small></div>
        <div><span>${summary.dry_run || 0}</span><small>드라이런</small></div>
        <div><span>${summary.failed || 0}</span><small>실패</small></div>
        <div><span>${status.configured ? "OK" : "미설정"}</span><small>텔레그램 설정</small></div>
      `;
    }
    renderDispatchPolicy(center);
    renderDispatchRows("#dispatchPendingRows", center.pending || [], "대기 보고 없음");
    renderDispatchRows("#dispatchRecentRows", center.dispatch_recent || [], "처리 기록 없음");
  } catch (error) {
    setText("dispatchState", "조회 실패");
    addLog(`텔레그램 발송 센터 조회 실패: ${error.message}`);
  }
}

async function dispatchTelegramReports() {
  try {
    const response = await fetch("/api/telegram/dispatch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 3, source: "ui-dispatch" }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "보고 처리 실패");
    addLog(`텔레그램 보고 처리: ${result.processed || 0}건`);
    await loadDispatchCenter();
    await loadOpsStatus();
  } catch (error) {
    addLog(`텔레그램 보고 처리 실패: ${error.message}`);
  }
}

function renderKrRows(title, rows = []) {
  return `
    <div class="kr-market-block">
      <strong>${title}</strong>
      ${rows.slice(0, 6).map((row) => `
        <div class="kr-market-line">
          <span>${escapeHtml(symbolDisplayName(row.symbol, row))}</span>
          <b class="${Number(row.change_pct || 0) >= 0 ? "up" : "down"}">${pct(row.change_pct || 0)}</b>
          <small>${row.market || "-"} · 거래대금 ${Math.round(Number(row.amount || 0) / 100000000).toLocaleString()}억</small>
        </div>
      `).join("")}
    </div>
  `;
}

async function loadKrMarketAnalysis() {
  setText("krMarketDate", "분석 중");
  try {
    const response = await fetch("/api/market/kr/today");
    const result = await response.json();
    if (!response.ok) return addLog(result.error || "한국장 분석 실패");
    setText("krMarketDate", `${result.date} · ${result.source}`);
    setText("krMarketStance", result.stance || "-");
    setText("krMarketBreadth", `${result.overall?.up || 0}/${result.overall?.down || 0}`);
    setText("krKospiPulse", `${pct(result.kospi?.marcap_weighted_change_pct || 0)} · 상승 ${Number(result.kospi?.up_ratio_pct || 0).toFixed(1)}%`);
    setText("krKosdaqPulse", `${pct(result.kosdaq?.marcap_weighted_change_pct || 0)} · 상승 ${Number(result.kosdaq?.up_ratio_pct || 0).toFixed(1)}%`);
    const semis = result.semiconductor || {};
    el("#krMarketRows").innerHTML = `
      <div class="kr-market-headline">${result.headline}<br><small>${result.calendar_note || ""}</small></div>
      ${renderKrRows("거래대금 상위", result.top_amount || [])}
      ${renderKrRows("상승률 상위", result.gainers || [])}
      ${renderKrRows("하락률 상위", result.losers || [])}
      ${renderKrRows("반도체/후공정 후보", semis.leaders || [])}
    `;
    addLog(`한국장 분석: ${result.date} ${result.stance}`);
  } catch (error) {
    setText("krMarketDate", "분석 실패");
    addLog(`한국장 분석 실패: ${error.message}`);
  }
}

function renderMissionList(selector, rows, emptyText) {
  const node = el(selector);
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.map((row) => {
      if (row.leaders) {
        const leaders = (row.leaders || []).slice(0, 3).map((item) => `${symbolDisplayName(item.symbol, item)} ${pct(item.change_pct || 0)}`).join(" · ");
        return `<div class="mission-item"><strong>${escapeHtml(row.name)}</strong><span>${pct(row.avg_change_pct || 0)} · ${row.count || 0}종목</span><small>${escapeHtml(replaceSymbolCodesInText(leaders || row.mission || ""))}</small></div>`;
      }
      return `<div class="mission-item"><strong>${escapeHtml(row.step || "-")}</strong><span>${escapeHtml(row.state || "-")}</span><small>${escapeHtml(replaceSymbolCodesInText(row.detail || ""))}</small></div>`;
    }).join("")
    : `<div class="mission-item"><strong>${emptyText}</strong><small>미션 실행을 누르면 자동으로 채워집니다.</small></div>`;
}

function renderMarketClock(clock = {}) {
  const rows = Array.isArray(clock.sessions) ? clock.sessions : [];
  const rowNode = el("#marketClockRows");
  const taskNode = el("#marketClockTasks");
  setText("marketClockFocus", clock.primary_focus || "시장 상태 확인 중");
  if (rowNode) {
    rowNode.innerHTML = rows.length
      ? rows.map((row) => {
        const klass = row.phase === "regular" ? "open" : row.phase === "premarket" || row.phase === "afterhours" ? "watch" : "closed";
        const symbols = (row.watch_symbols || []).slice(0, 5).map((symbol) => symbolDisplayName(symbol)).join(" · ");
        return `
          <div class="market-clock-card ${klass}">
            <div><strong>${row.name || "-"}</strong><span>${row.phase_label || "-"}</span></div>
            <p>${row.market_time || "-"}</p>
            <small>${row.next_event || "다음 이벤트"}까지 ${row.minutes_to_next ?? "-"}분 · ${symbols}</small>
          </div>
        `;
      }).join("")
      : `<div class="market-clock-card closed"><div><strong>시장 시계 대기</strong><span>-</span></div><p>데이터 수신 대기</p></div>`;
  }
  if (taskNode) {
    const tasks = Array.isArray(clock.tasks) ? clock.tasks : [];
    taskNode.innerHTML = tasks.length
      ? tasks.map((task) => `<span>${escapeHtml(replaceSymbolCodesInText(task))}</span>`).join("")
      : `<span>AI 시장 감시 작업을 계산 중입니다.</span>`;
  }
}

async function loadMarketClock() {
  try {
    const response = await fetch("/api/agent/market-clock");
    const clock = await response.json();
    renderMarketClock(clock);
  } catch (error) {
    setText("marketClockFocus", "시장 시계 조회 실패");
    addLog(`시장 시계 조회 실패: ${error.message}`);
  }
}

function renderMarketRegime(regime = {}) {
  const auto = regime.automation || {};
  setText("marketRegimeState", `${regime.stance || "대기"} · ${Number(regime.score || 0).toFixed(1)}/100`);
  setText("marketRegimeBrief", regime.headline || "시장 국면 계산 대기 중");
  const summaryNode = el("#marketRegimeSummary");
  if (summaryNode) {
    summaryNode.innerHTML = `
      <div><span>${Number(regime.score || 0).toFixed(1)}</span><small>국면 점수</small></div>
      <div><span>${escapeHtml(regime.stance || "-")}</span><small>운영 모드</small></div>
      <div><span>${escapeHtml(auto.cash_range || "-")}</span><small>권장 현금</small></div>
      <div><span>${Number(auto.allocation_multiplier ?? 1).toFixed(2)}x</span><small>목표금액 배율</small></div>
      <div><span>${auto.new_buy_blocked ? "차단" : "허용"}</span><small>신규 BUY</small></div>
    `;
  }
  const signalNode = el("#marketRegimeSignals");
  const assets = Array.isArray(regime.assets) ? regime.assets : [];
  if (signalNode) {
    signalNode.innerHTML = assets.length
      ? assets.map((item) => `
        <div class="market-regime-card gear-${Number(item.gear || 0)}">
          <strong>${escapeHtml(item.symbol ? symbolDisplayName(item.symbol, item) : item.label || "-")}</strong>
          <b>Gear ${escapeHtml(item.gear ?? "-")} · ${escapeHtml(item.state || "-")}</b>
          <small>${Number(item.price || 0).toLocaleString()} · 200일선 ${Number(item.distance_200d_pct || 0).toFixed(2)}% · 30주선 ${Number(item.distance_30w_pct || 0).toFixed(2)}%</small>
        </div>
      `).join("")
      : `<div class="market-regime-card"><strong>신호 대기</strong><small>시장 데이터를 불러오는 중입니다.</small></div>`;
  }
  const ruleNode = el("#marketRegimeRules");
  if (ruleNode) {
    const breadth = regime.breadth || {};
    const volatility = regime.volatility || {};
    const rules = Array.isArray(regime.rules) ? regime.rules : [];
    ruleNode.innerHTML = `
      <div class="market-regime-card ${auto.leverage_allowed ? "ok" : "warn"}">
        <strong>자동운영 제한</strong>
        <b>${auto.leverage_allowed ? "레버리지 일부 허용" : "레버리지 금지"}</b>
        <small>3-3-4 분할: ${(auto.tranches || []).join(" / ") || "-"} · 최대 레버리지 ${auto.max_leverage_position_pct || 0}%</small>
      </div>
      <div class="market-regime-card ${Number(breadth.rsp_minus_spy_4w_pct || 0) < -1.5 ? "warn" : "ok"}">
        <strong>시장 참여폭</strong>
        <b>${escapeHtml(breadth.state || "-")}</b>
        <small>RSP-SPY 4주 ${Number(breadth.rsp_minus_spy_4w_pct || 0).toFixed(2)}%</small>
      </div>
      <div class="market-regime-card ${Number(volatility.vix || 0) > 20 ? "warn" : "ok"}">
        <strong>VIX 변동성</strong>
        <b>${Number(volatility.vix || 0).toFixed(2)}</b>
        <small>${escapeHtml(volatility.state || "-")}</small>
      </div>
      ${rules.slice(0, 4).map((rule) => `<div class="market-regime-card"><strong>규칙</strong><small>${escapeHtml(rule)}</small></div>`).join("")}
    `;
  }
}

async function loadMarketRegime(force = false) {
  try {
    const response = await fetch(`/api/market/regime${force ? "?force=1" : ""}`);
    const regime = await response.json();
    renderMarketRegime(regime);
  } catch (error) {
    setText("marketRegimeState", "조회 실패");
    setText("marketRegimeBrief", `시장 국면 조회 실패: ${error.message}`);
  }
}

function renderAutopilotRuns(rows = []) {
  const node = el("#autopilotRuns");
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 8).map((row) => {
      const steps = Array.isArray(row.executed) ? row.executed : [];
      const stepText = steps.slice(0, 4).map((item) => `${item.step}:${item.status}`).join(" · ");
      return `
        <div class="autopilot-run">
          <div><strong>${row.id || "-"}</strong><span>${row.mode || "-"} · ${escapeHtml(realExecutionLabel(row.real_execution || "BLOCKED"))}</span></div>
          <p>${row.message || ""}</p>
          <small>${row.created_at || "-"} · ${stepText}</small>
        </div>
      `;
    }).join("")
    : `<div class="autopilot-run"><strong>실행 기록 대기</strong><p>안전 틱 실행을 누르면 AI가 점검한 내용이 여기에 남습니다.</p></div>`;
}

function renderDashboardWorker(plan = {}) {
  const summary = plan.summary || {};
  const scheduler = plan.scheduler || {};
  const runs = Array.isArray(plan.recent_runs) ? plan.recent_runs : [];
  const latest = runs[0] || scheduler.last_tick || {};
  const running = Boolean(summary.autopilot_running || scheduler.running);
  setText("dashWorkerMode", `${summary.mode || "시장 감시/연구"} · ${summary.primary_market || "-"} ${summary.phase || ""}`);
  setText("dashWorkerRunning", running ? "작동 중" : "대기");
  const runningNode = el("#dashWorkerRunning");
  if (runningNode) runningNode.className = running ? "on" : "idle";
  setText("dashWorkerRole", "후보발굴 · 백테스트 · 과거장훈련 · 리스크점검");
  setText("dashWorkerLastAction", latest.message || `${latest.mode || "-"} ${latest.id || ""}`.trim() || "아직 실행 기록 없음");
  setText("dashWorkerNext", summary.next_check_at || "-");
  setText("dashWorkerReports", "장전/장중/마감/복기/21시 + 매매사유");
  setText("dashWorkerNote", plan.safety || "대시보드는 사람이 보는 관제실이고, 실제 반복 작업은 AI 작업자가 백그라운드에서 수행합니다.");
}

function renderAutopilotHealth(health = {}) {
  const node = el("#autopilotHealth");
  if (!node) return;
  const summary = health.summary || {};
  const checks = Array.isArray(health.checks) ? health.checks : [];
  const statusLabel = {
    ok: "정상",
    warning: "주의",
    critical: "위험",
    idle: "대기",
  };
  node.innerHTML = `
    <div class="autopilot-health-main ${summary.overall || "idle"}">
      <b>${statusLabel[summary.overall] || summary.overall || "대기"}</b>
      <span>최근 틱 ${summary.last_run_age_minutes ?? "-"}분 · 최근보고 ${summary.recent_reports || 0}/${summary.pending_reports || 0}건 · 승인 ${summary.pending_approvals || 0}건</span>
      <small>시세 ${escapeHtml(summary.quote_symbol ? symbolDisplayName(summary.quote_symbol) : "-")} ${money0(summary.quote_price || 0)} ${summary.quote_source || "-"} · 텔레그램 명령 ${summary.telegram_poller_running ? "켜짐" : "꺼짐"} / 자동보고 ${summary.telegram_dispatcher_running ? "켜짐" : "꺼짐"} · 실전 주문 ${escapeHtml(realExecutionLabel(summary.real_execution || "BLOCKED"))}</small>
    </div>
    ${checks.slice(0, 8).map((item) => `
      <div class="autopilot-health-check ${item.status || "idle"}">
        <strong>${item.label || "-"}</strong>
        <span>${statusLabel[item.status] || item.status || "-"}</span>
        <small>${item.detail || ""}</small>
      </div>
    `).join("")}
  `;
}

function renderHealthSnapshots(rows = []) {
  const node = el("#healthSnapshotRows");
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 6).map((row) => {
      const klass = row.changed ? "changed" : String(row.overall || "idle");
      const problemCount = Array.isArray(row.problem_checks) ? row.problem_checks.length : 0;
      return `
        <div class="health-snapshot-item ${klass}">
          <strong>${row.overall || "-"} ${row.changed ? "변화" : "유지"}</strong>
          <span>${row.created_at || "-"} · ${escapeHtml(row.quote_symbol ? symbolDisplayName(row.quote_symbol) : "-")} ${money0(row.quote_price || 0)} · ${row.quote_source || "-"}</span>
          <small>문제 ${problemCount}개 · 최근보고 ${row.recent_reports || 0}/${row.pending_reports || 0}건 · ${row.health_report_id ? `보고 ${row.health_report_id}` : "보고 없음"}</small>
        </div>
      `;
    }).join("")
    : `<div class="health-snapshot-item idle"><strong>건강 스냅샷 대기</strong><small>오토파일럿 안전 틱이 돌면 상태 변화 기준선이 쌓입니다.</small></div>`;
}

async function loadHealthSnapshots() {
  try {
    const response = await fetch("/api/agent/health-snapshots?limit=6");
    const result = await response.json();
    renderHealthSnapshots(result.snapshots || []);
  } catch (error) {
    addLog(`건강 스냅샷 조회 실패: ${error.message}`);
  }
}

function renderAutopilot(plan = {}) {
  const summary = plan.summary || {};
  const scheduler = plan.scheduler || {};
  const continuousTraining = plan.continuous_training || {};
  const nextTraining = continuousTraining.next_task || {};
  const trainingWaitMin = Math.max(0, Math.ceil(Number(continuousTraining.due_in_seconds || 0) / 60));
  const trainingLabel = continuousTraining.running
    ? "훈련 중"
    : continuousTraining.due
      ? "훈련 가능"
      : `${trainingWaitMin}분 후`;
  renderDashboardWorker(plan);
  setText("autopilotState", `${summary.mode || "대기"} · 자동점검 ${summary.autopilot_running ? "켜짐" : "꺼짐"} · ${realExecutionLabel(summary.real_execution || "BLOCKED")}`);
  setText("autopilotBrief", `${plan.headline || "-"} ${plan.stance || ""}`);
  setText("autopilotSafety", `${koreanStatusText(plan.safety || "실전 주문은 잠금입니다.")} ${scheduler.last_error ? `최근 오류: ${scheduler.last_error}` : ""}`);
  const summaryNode = el("#autopilotSummary");
  if (summaryNode) {
    summaryNode.innerHTML = `
      <div><span>${summary.primary_market || "-"}</span><small>주 시장</small></div>
      <div><span>${summary.phase || "-"}</span><small>세션</small></div>
      <div><span>${summary.cadence_minutes || 0}분</span><small>점검 주기</small></div>
      <div><span>${summary.candidate_count || 0}</span><small>후보</small></div>
      <div><span>${summary.paper_rehearsal_snapshot_count || 0}</span><small>리허설 기억</small></div>
      <div><span>${summary.paper_rehearsal_avg_delta_pct ?? 0}%p</span><small>${summary.paper_rehearsal_trend || "변화 대기"}</small></div>
      <div><span>${summary.pending_reports || 0}</span><small>보고 대기</small></div>
      <div><span>${escapeHtml(trainingLabel)}</span><small>연속훈련 · ${escapeHtml(nextTraining.task || "대기")}</small></div>
      <div><span>${summary.autopilot_running ? "켜짐" : "꺼짐"}</span><small>자동 점검</small></div>
    `;
  }
  renderAutopilotHealth(plan.health || {});
  loadHealthSnapshots();
  const actionsNode = el("#autopilotActions");
  const actions = Array.isArray(plan.actions) ? plan.actions : [];
  if (actionsNode) {
    actionsNode.innerHTML = actions.length
      ? actions.map((item) => `
        <div class="autopilot-item ${item.state || "wait"}">
          <div><strong>${item.title || "-"}</strong><span>${item.state || "-"}</span></div>
          <p>${item.detail || ""}</p>
          <small>${item.command ? `명령 힌트: ${item.command}` : ""}</small>
        </div>
      `).join("")
      : `<div class="autopilot-item wait"><strong>행동 계산 대기</strong><p>시장 시계와 파이프라인을 읽는 중입니다.</p></div>`;
  }
  const lanesNode = el("#autopilotLanes");
  const lanes = Array.isArray(plan.lanes) ? plan.lanes : [];
  if (lanesNode) {
    lanesNode.innerHTML = lanes.length
      ? lanes.map((row) => `
        <div class="autopilot-item lane">
          <div><strong>${escapeHtml(symbolDisplayName(row.symbol, row))}</strong><span>${row.lane || "-"}</span></div>
          <p>점수 ${row.score || "-"} · 게이트 ${row.gate || "-"} · 진행 ${Number(row.progress || 0).toFixed(0)}%</p>
          <small>${escapeHtml(replaceSymbolCodesInText(row.next_action || ""))}</small>
        </div>
      `).join("")
      : `<div class="autopilot-item wait"><strong>감시 레인 대기</strong><p>후보 파이프라인이 채워지면 여기에 표시됩니다.</p></div>`;
  }
  renderAutopilotRuns(plan.recent_runs || []);
}

async function loadAutopilot() {
  try {
    const response = await fetch("/api/agent/autopilot");
    const plan = await response.json();
    renderAutopilot(plan);
  } catch (error) {
    setText("autopilotState", "조회 실패");
    addLog(`AI 오토파일럿 조회 실패: ${error.message}`);
  }
}

async function runAutopilotTick() {
  try {
    setText("autopilotState", "안전 틱 실행 중");
    const response = await fetch("/api/agent/autopilot/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "ui-autopilot", deep: false }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "오토파일럿 실행 실패");
    renderAutopilot(result.plan || {});
    renderAutopilotRuns(result.recent || []);
    await loadHealthSnapshots();
    addLog(`AI 오토파일럿 안전 틱: ${result.record?.id || "-"} / ${result.record?.mode || "-"}`);
    await loadWorklog();
  } catch (error) {
    setText("autopilotState", "실행 실패");
    addLog(`AI 오토파일럿 실행 실패: ${error.message}`);
  }
}

async function queueHealthReport() {
  try {
    setText("autopilotState", "건강보고 생성 중");
    const response = await fetch("/api/agent/health-report/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "ui-health-report" }),
    });
    const result = await response.json();
    if (!response.ok && response.status !== 202) throw new Error(result.error || "건강보고 생성 실패");
    addLog(`AI 건강보고 기록: ${result.note_path || "-"} / 텔레그램 ${result.telegram_record?.id || "-"}`);
    if (result.health) renderAutopilotHealth(result.health);
    await loadDispatchCenter();
    await loadAutopilot();
    await loadHealthSnapshots();
  } catch (error) {
    setText("autopilotState", "건강보고 실패");
    addLog(`AI 건강보고 실패: ${error.message}`);
  }
}

async function controlAutopilotScheduler(action) {
  try {
    setText("autopilotState", action === "start" ? "자동 점검 시작 중" : "자동 점검 정지 중");
    const response = await fetch(action === "start" ? "/api/agent/autopilot/start" : "/api/agent/autopilot/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "ui-autopilot" }),
    });
    const status = await response.json();
    if (!response.ok) throw new Error(status.error || "오토파일럿 자동 점검 제어 실패");
    addLog(`AI 오토파일럿 자동 점검 ${action === "start" ? "시작" : "정지"}: ${status.running ? "켜짐" : "꺼짐"}`);
    await loadAutopilot();
  } catch (error) {
    setText("autopilotState", "자동 점검 제어 실패");
    addLog(`AI 오토파일럿 자동 점검 제어 실패: ${error.message}`);
  }
}

async function loadMission() {
  try {
    const response = await fetch("/api/agent/mission");
    const mission = await response.json();
    setText("missionState", mission.running ? "24시간 연구 중" : "대기");
    setText("missionObjective", mission.objective || "-");
    setText("missionCycleCount", `${mission.cycle_count || 0}회`);
    setText("missionReplayCount", `${mission.historical_replay_memory_count || 0}개`);
    setText("missionKnowledgeGraph", `${mission.knowledge_graph?.node_count || 0}/${mission.knowledge_graph?.edge_count || 0}`);
    setText("missionLatestDay", mission.latest_trading_day || "-");
    setText("missionSourceCount", `${(mission.sources || []).length}개`);
    setText("missionSafety", mission.safety || "주문잠금");
    renderMarketClock(mission.market_clock || {});
    renderMissionList("#missionThemes", mission.themes || [], "테마 분석 대기");
    renderMissionList("#missionTasks", mission.task_queue || [], "작업 큐 대기");
  } catch (error) {
    setText("missionState", "조회 실패");
    addLog(`AI 미션 조회 실패: ${error.message}`);
  }
}

function renderWorklogTimeline(selector, rows = [], emptyText = "근무 기록 대기") {
  const node = el(selector);
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 12).map((row) => {
      const badgeMap = {
        staff_activity: "근무",
        staff_meeting: "회의",
        cycle: "연구",
        journal: "기록",
      };
      const badge = badgeMap[row.kind] || "기록";
      const score = row.score !== "" && row.score !== undefined ? ` · 점수 ${row.score}` : "";
      const gate = row.gate ? ` · 게이트 ${row.gate}` : "";
      const ops = row.ops_status ? ` · OPS ${row.ops_status}` : "";
      return `
        <div class="worklog-item">
          <div><b>${badge}</b><strong>${row.title || "-"}</strong></div>
          <span>${row.created_at || "-"}</span>
          <p>${row.headline || "-"}</p>
          <small>${row.symbol ? escapeHtml(symbolDisplayName(row.symbol, row)) : ""}${score}${gate}${ops}</small>
        </div>
      `;
    }).join("")
    : `<div class="worklog-item"><strong>${emptyText}</strong><p>AI 연구 사이클이 실행되면 여기에 기록됩니다.</p></div>`;
}

function renderWorklogLessons(selector, rows = [], emptyText = "복기 메모 대기") {
  const node = el(selector);
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice().reverse().map((item, index) => `
      <div class="worklog-item compact">
        <div><b>${index + 1}</b><strong>학습 메모</strong></div>
        <p>${item}</p>
      </div>
    `).join("")
    : `<div class="worklog-item compact"><strong>${emptyText}</strong><p>사이클 복기가 쌓이면 표시됩니다.</p></div>`;
}

function renderWorklogCandidates(selector, rows = []) {
  const node = el(selector);
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 10).map((row, index) => `
      <div class="worklog-item compact">
        <div><b>${index + 1}</b><strong>${escapeHtml(symbolDisplayName(row.symbol, row))}</strong></div>
        <span>점수 ${row.score || "-"} · 게이트 ${row.gate || "-"} · 강건성 ${row.robustness_score || "-"}</span>
        <p>${row.memo || "후보 기억 유지 중"}</p>
      </div>
    `).join("")
    : `<div class="worklog-item compact"><strong>후보 기억 대기</strong><p>AI가 후보를 평가하면 여기에 누적됩니다.</p></div>`;
}

async function loadWorklog() {
  try {
    const response = await fetch("/api/agent/worklog");
    const worklog = await response.json();
    const brief = worklog.brief || {};
    setText("worklogState", realExecutionLabel(worklog.ops_snapshot?.real_execution || "BLOCKED"));
    setText("journalWorklogState", worklog.generated_at || "대기");
    setText("worklogBrief", replaceSymbolCodesInText(`${brief.summary || "-"} 다음 행동: ${brief.next_action || "-"}`));
    const cards = worklog.shift_cards || [];
    const cardNode = el("#worklogCards");
    if (cardNode) {
      cardNode.innerHTML = cards.length
        ? cards.map((card) => `<div><span>${card.value || "-"}</span><small>${card.label || "-"} · ${card.detail || ""}</small></div>`).join("")
        : `<div><span>-</span><small>교대보고 대기</small></div>`;
    }
    renderWorklogTimeline("#worklogTimeline", worklog.timeline || [], "근무 기록 대기");
    renderWorklogTimeline("#journalWorklogTimeline", worklog.timeline || [], "근무 기록 대기");
    renderWorklogLessons("#worklogLessons", worklog.lessons || [], "복기 메모 대기");
    renderWorklogCandidates("#journalWorklogCandidates", worklog.top_candidates || []);
  } catch (error) {
    setText("worklogState", "조회 실패");
    setText("journalWorklogState", "조회 실패");
    addLog(`AI 근무일지 조회 실패: ${error.message}`);
  }
}

function renderPipeline(pipeline = {}) {
  const summary = pipeline.summary || {};
  const rows = Array.isArray(pipeline.candidates) ? pipeline.candidates : [];
  setText("pipelineState", pipeline.safety || "실전 주문 잠금");
  const summaryNode = el("#pipelineSummary");
  if (summaryNode) {
    summaryNode.innerHTML = `
      <div><span>${summary.count || 0}</span><small>후보</small></div>
      <div><span>${summary.paper_ready || 0}</span><small>리허설 대기</small></div>
      <div><span>${summary.observing || 0}</span><small>관찰</small></div>
      <div><span>${summary.dry_run_ready || 0}</span><small>Dry-run 대기</small></div>
      <div><span>${summary.blocked || 0}</span><small>검토/차단</small></div>
      <div><span>${escapeHtml(realExecutionLabel(summary.real_execution || "BLOCKED"))}</span><small>실전 주문</small></div>
    `;
  }
  const rowNode = el("#pipelineRows");
  if (!rowNode) return;
  rowNode.innerHTML = rows.length
    ? rows.slice(0, 10).map((row) => {
      const stages = row.stages || [];
      const stageHtml = stages.map((stage) => `<span class="pipeline-stage ${stage.state || "wait"}">${stage.label}</span>`).join("");
      return `
        <div class="pipeline-row">
          <div class="pipeline-main">
            <div>
              <strong>${escapeHtml(symbolDisplayName(row.symbol, row))}</strong>
              <small>${row.market || "-"} · ${row.lane || "-"} · 게이트 ${row.gate || "-"} · 점수 ${Number(row.score || 0).toFixed(1)}</small>
              <small>공개시세 ${row.market_signal_label || "-"} · 보조점수 ${Number(row.market_signal_score_delta || 0).toFixed(1)}</small>
            </div>
            <b>${Number(row.progress || 0).toFixed(0)}%</b>
          </div>
          <div class="pipeline-bar"><i style="width:${Math.max(3, Number(row.progress || 0))}%"></i></div>
          <div class="pipeline-stages">${stageHtml}</div>
          <p>${escapeHtml(replaceSymbolCodesInText(row.next_action || "다음 행동 대기"))}</p>
        </div>
      `;
    }).join("")
    : `<div class="pipeline-row"><strong>파이프라인 대기</strong><p>AI 후보 발굴이 실행되면 처리 단계가 표시됩니다.</p></div>`;
}

async function loadPipeline() {
  try {
    const response = await fetch("/api/agent/pipeline");
    const pipeline = await response.json();
    renderPipeline(pipeline);
  } catch (error) {
    setText("pipelineState", "조회 실패");
    addLog(`AI 파이프라인 조회 실패: ${error.message}`);
  }
}

function renderNewsRadar(rows = []) {
  const node = el("#newsRadarRows");
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 8).map((row) => {
      const first = (row.items || [])[0] || {};
      const link = first.link ? `<a href="${first.link}" target="_blank" rel="noreferrer">기사 열기</a>` : "";
      const title = replaceSymbolCodesInText(first.title || row.message || "뉴스 대기");
      return `
        <div class="radar-item">
          <strong>${escapeHtml(symbolDisplayName(row.symbol, row))}</strong>
          <span>${row.stance || "-"} · 점수 ${row.score || 0}</span>
          <small>${escapeHtml(title)} ${link}</small>
        </div>
      `;
    }).join("")
    : `<div class="radar-item"><strong>뉴스 대기</strong><small>레이더 실행을 누르면 최신 뉴스/리포트를 훑습니다.</small></div>`;
}

function renderFinancialRadar(rows = []) {
  const node = el("#financialRadarRows");
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 8).map((row) => {
      const display = row.display || {};
      return `
        <div class="radar-item">
          <strong>${escapeHtml(symbolDisplayName(row.symbol, row))}</strong>
          <span>${row.stance || "-"} · 점수 ${row.score || 0}</span>
          <small>매출 ${display.revenue || "-"} · 영업이익 ${display.operating_income || "-"} · 부채비율 ${display.debt_ratio || "-"}</small>
          <small>${row.message || ""}</small>
        </div>
      `;
    }).join("")
    : `<div class="radar-item"><strong>재무 대기</strong><small>DART 연결 종목은 재무제표를 자동 점검합니다.</small></div>`;
}

function renderRadarTasks(tasks = []) {
  const node = el("#radarTasks");
  if (!node) return;
  node.innerHTML = tasks.length
    ? tasks.slice(0, 10).map((task) => `<div class="radar-item"><strong>작업</strong><small>${escapeHtml(replaceSymbolCodesInText(task))}</small></div>`).join("")
    : `<div class="radar-item"><strong>대기</strong><small>특이 작업 지시가 없습니다.</small></div>`;
}

function renderScreenerRows(rows = []) {
  const node = el("#screenerRows");
  if (!node) return;
  state.recommendations = rows;
  node.innerHTML = rows.length
    ? rows.slice(0, 12).map((row, index) => {
      const reasons = (row.reasons || []).slice(0, 3).join(" · ");
      const risks = (row.risk_flags || []).slice(0, 2).join(" · ");
      const klass = Number(row.score || 0) >= 80 ? "up" : Number(row.score || 0) >= 60 ? "flat" : "down";
      const rawScore = row.raw_score !== undefined && row.raw_score !== null ? Number(row.raw_score || 0) : null;
      const adjustedScore = Number(row.score || 0);
      const scoreNormalization = row.score_adjustment || row.score_normalization || {};
      const scoreLine = rawScore !== null && Math.abs(rawScore - adjustedScore) >= 0.05
        ? `raw ${rawScore.toFixed(1)} -> soft-cap ${adjustedScore.toFixed(1)}`
        : `raw ${Number(row.score || 0).toFixed(1)}`;
      const scorePolicyLine = scoreNormalization.compressed || scoreNormalization.saturated ? "100점 포화 방지 압축 적용" : "";
      const duplicateRemoved = Number(row.duplicate_bonus_removed || 0);
      const duplicatePolicyLine = duplicateRemoved > 0.01 ? `중복 가점 ${duplicateRemoved.toFixed(1)}점 제거` : "";
      const marketSignal = row.market_signal || {};
      const signal = marketSignal.signal || {};
      const signalDelta = Number(row.market_signal_score_delta || signal.score_delta || 0);
      const signalClass = signalDelta > 0 ? "up" : signalDelta < 0 ? "down" : "flat";
      const signalLine = marketSignal.ok
        ? `토스 공개시세 ${signal.label || "-"} ${signalDelta >= 0 ? "+" : ""}${signalDelta.toFixed(1)} · 현재가 ${money0(marketSignal.price)} · 등락 ${pct(marketSignal.change_pct || 0)} · RSI ${marketSignal.rsi14 ?? "-"}`
        : "";
      const sectorSignal = row.sector_news_signal || {};
      const sectorDelta = Number(row.sector_news_score_delta || sectorSignal.score_delta || 0);
      const sectorClass = sectorDelta > 0 ? "up" : sectorDelta < 0 ? "down" : "flat";
      const sectorLine = sectorSignal.matched
        ? `섹터뉴스 ${sectorSignal.label || "-"} ${sectorDelta >= 0 ? "+" : ""}${sectorDelta.toFixed(1)} · ${sectorSignal.detail || ""}`
        : "";
      return `
        <div class="screener-row" data-dossier-symbol="${row.symbol}">
          <b>${index + 1}</b>
          <div>
            <strong>${escapeHtml(symbolDisplayName(row.symbol, row))}</strong>
            <small>${row.market || "-"} · ${row.action || "-"} · 재무 ${row.financial_stance || "-"} · 뉴스 ${row.news_stance || "-"}</small>
            ${signalLine ? `<small class="${signalClass}">${signalLine}</small>` : ""}
            ${sectorLine ? `<small class="${sectorClass}">${sectorLine}</small>` : ""}
            <small>게이트 ${row.risk_gate_status || "-"} · 이유: ${reasons || "데이터 누적 관찰"}</small>
            ${risks ? `<small class="down">주의: ${risks}</small>` : ""}
          </div>
          <div>
            <span class="${klass}">${Number(row.score || 0).toFixed(1)}</span>
            <small>${scoreLine}</small>
            ${scorePolicyLine ? `<small class="flat">${scorePolicyLine}</small>` : ""}
            ${duplicatePolicyLine ? `<small class="flat">${duplicatePolicyLine}</small>` : ""}
            <small>수익 ${pct(row.return_pct || 0)} · MDD ${pct(row.mdd_pct || 0)}</small>
          </div>
        </div>
      `;
    }).join("")
    : `<div class="screener-row"><b>-</b><div><strong>후보 대기</strong><small>후보 발굴을 누르면 AI가 종목을 점수화합니다.</small></div><div><span>-</span></div></div>`;
}

function renderOpportunityCard(card = {}, compact = false) {
  const score = Number(card.score || 0);
  const klass = score >= 80 ? "up" : score >= 60 ? "flat" : "down";
  const upside = card.upside || {};
  const style = card.investor_style || {};
  const financial = card.financial || {};
  const news = card.news || {};
  const signal = card.sector_signal || {};
  const backtest = card.backtest || {};
  const quality = card.company_quality || {};
  const qualityScore = Number(card.quality_score || quality.score || 0);
  const qualityGrade = card.quality_grade || quality.grade || "-";
  const qualityPassed = Boolean(card.quality_passed || quality.is_quality_candidate);
  const trade = card.trade_horizon || {};
  const tradeMode = card.trade_mode || trade.mode || "-";
  const why = Array.isArray(card.why) ? card.why.slice(0, compact ? 2 : 4) : [];
  const risks = Array.isArray(card.risks) ? card.risks.slice(0, compact ? 1 : 3) : [];
  const study = Array.isArray(card.next_study) ? card.next_study.slice(0, 2) : [];
  const links = (Array.isArray(card.news_links) && card.news_links.length ? card.news_links : card.sector_news_links || []).slice(0, compact ? 2 : 3);
  const linkHtml = links.length
    ? `<div class="opportunity-links">${links.map((item) => {
      const href = escapeHtml(item.link || "#");
      const title = replaceSymbolCodesInText(item.title || "");
      return `<a href="${href}" target="_blank" rel="noreferrer" title="${escapeHtml(title)}">${escapeHtml(item.source || "기사")} · ${escapeHtml(String(title).slice(0, 42))}</a>`;
    }).join("")}</div>`
    : "";
  return `
    <article class="opportunity-card ${compact ? "compact" : ""}" data-dossier-symbol="${escapeHtml(card.symbol || "")}">
      <div class="opportunity-card-top">
        <div>
          <strong>${escapeHtml(symbolDisplayName(card.symbol, card))}</strong>
          <small>${escapeHtml(card.market || "-")} · ${escapeHtml(card.action || "-")} · ${escapeHtml(card.price_source || "-")}</small>
        </div>
        <span class="${klass}">${score.toFixed(1)}</span>
      </div>
      <div class="opportunity-price-line">
        <b>${money0(card.price || 0)}</b>
        <span class="${Number(card.change_pct || 0) >= 0 ? "up" : "down"}">${pct(card.change_pct || 0)}</span>
        <small>${escapeHtml(upside.text || "상승여력 가설 대기")} · 신뢰 ${escapeHtml(upside.confidence || "-")}</small>
      </div>
      <div class="opportunity-trade-mode">
        <b>${escapeHtml(tradeMode)}</b>
        <span>단타 ${Number(trade.daytrade_score || 0).toFixed(0)} · 스윙 ${Number(trade.swing_score || 0).toFixed(0)}</span>
        <small>${escapeHtml(trade.hold_rule || "AI가 매매 기간을 자동 판단합니다.")}</small>
      </div>
      <div class="opportunity-style">
        <b>${escapeHtml(style.primary || "-")}</b>
        <span>적합도 ${Number(style.fit_score || 0).toFixed(1)}</span>
        <small>${escapeHtml(style.why || "")}</small>
      </div>
      <div class="opportunity-metrics">
        <div><b>${escapeHtml(qualityGrade)}</b><small>품질 ${qualityPassed ? "통과" : "점검"} · ${qualityScore.toFixed(0)}</small></div>
        <div><b>${Number(financial.score || 0).toFixed(0)}</b><small>재무 ${escapeHtml(financial.stance || "-")}</small></div>
        <div><b>${Number(news.score || 0).toFixed(0)}</b><small>뉴스 ${escapeHtml(news.stance || "-")}</small></div>
        <div><b>${Number(signal.score_delta || 0).toFixed(1)}</b><small>섹터 ${escapeHtml(signal.label || "-")}</small></div>
        <div><b>${pct(backtest.return_pct || 0)}</b><small>MDD ${pct(backtest.mdd_pct || 0)}</small></div>
      </div>
      ${why.length ? `<div class="opportunity-list good">${why.map((item) => `<small>${escapeHtml(replaceSymbolCodesInText(item))}</small>`).join("")}</div>` : ""}
      ${risks.length ? `<div class="opportunity-list risk">${risks.map((item) => `<small>${escapeHtml(replaceSymbolCodesInText(item))}</small>`).join("")}</div>` : ""}
      ${linkHtml}
      ${!compact && study.length ? `<div class="opportunity-list study">${study.map((item) => `<small>${escapeHtml(replaceSymbolCodesInText(item))}</small>`).join("")}</div>` : ""}
    </article>
  `;
}

function committeeGuardClass(status = "") {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "PASS") return "pass";
  if (normalized === "WATCH") return "watch";
  if (normalized === "BLOCK") return "block";
  return "idle";
}

function renderSectorCommittee(report = {}) {
  state.lastSectorCommittee = report;
  const chair = report.chair || {};
  const guard = report.concentration_guard || {};
  const guardStatus = String(guard.status || "-").toUpperCase();
  const guardClass = committeeGuardClass(guardStatus);
  setText("sectorCommitteeState", report.refreshing ? "캐시 · 갱신 중" : report.cached ? "캐시" : "최신");
  setText("sectorCommitteeApproval", chair.approval || "-");
  setText("sectorCommitteeCash", report.cash_weight_pct !== undefined ? `${Number(report.cash_weight_pct || 0).toFixed(1)}%` : "-");
  setText("sectorCommitteeGuard", guardStatus === "PASS" ? "정상" : guardStatus === "WATCH" ? "주의" : guardStatus === "BLOCK" ? "보류" : "-");
  setText("sectorCommitteeMax", guard.max_sector ? `${guard.max_sector} ${Number(guard.max_weight_pct || 0).toFixed(1)}%` : "-");
  setText("sectorCommitteeSummary", chair.summary || "업종 회의 결과 대기");
  setText("sectorCommitteeSafety", report.refresh_message || report.safety || "연구용 포트폴리오 초안입니다. 실전 주문은 실행하지 않습니다.");

  const rowsNode = el("#sectorCommitteeRows");
  const sectors = Array.isArray(report.sector_rankings) ? report.sector_rankings : [];
  if (rowsNode) {
    rowsNode.innerHTML = sectors.length
      ? sectors.slice(0, 8).map((sector, index) => {
        const reps = Array.isArray(sector.representatives) ? sector.representatives.slice(0, 2) : [];
        const basis = sector.rank_basis || {};
        const comps = sector.component_averages || {};
        const votes = sector.votes || {};
        const pros = Array.isArray(votes.pros) ? votes.pros.length : 0;
        const cons = Array.isArray(votes.cons) ? votes.cons.length : 0;
        return `
          <article class="sector-committee-card">
            <div class="sector-committee-card-top">
              <b>${index + 1}</b>
              <div>
                <strong>${escapeHtml(sector.name || "-")}</strong>
                <small>후보평균 ${Number(basis.candidate_avg_score || 0).toFixed(1)} · 품질 ${Number(basis.quality_avg || comps.quality || 0).toFixed(1)} · 집중 ${Number(basis.concentration_count_top12 || 0)}개</small>
              </div>
              <span>${Number(sector.committee_score || 0).toFixed(1)}</span>
            </div>
            <div class="sector-committee-reps">
              ${reps.length ? reps.map((rep) => `
                <div>
                  <strong>${escapeHtml(symbolDisplayName(rep.symbol, rep))}</strong>
                  <small>종목 ${Number(rep.score || 0).toFixed(1)} · 회의 ${Number(rep.committee_total_score || 0).toFixed(1)}</small>
                </div>
              `).join("") : `<div><strong>대표 종목 대기</strong><small>후보 데이터 부족</small></div>`}
            </div>
            <div class="sector-committee-components">
              <span>거시 ${Number(comps.macro || 0).toFixed(1)}</span>
              <span>재무 ${Number(comps.financial || 0).toFixed(1)}</span>
              <span>뉴스 ${Number(comps.news || 0).toFixed(1)}</span>
              <span>리스크 ${Number(comps.risk || 0).toFixed(1)}</span>
            </div>
            <small class="sector-committee-vote-line">찬성 ${pros} · 반대/주의 ${cons}</small>
          </article>
        `;
      }).join("")
      : `<div class="sector-committee-empty">업종 회의 결과 대기</div>`;
  }

  const portfolioNode = el("#sectorCommitteePortfolio");
  const portfolio = Array.isArray(report.portfolio) ? report.portfolio : [];
  if (portfolioNode) {
    portfolioNode.innerHTML = portfolio.length
      ? portfolio.map((item) => {
        const rep = item.representative || {};
        return `
          <div class="sector-committee-list-item">
            <strong>${escapeHtml(item.sector || "-")} <span>${Number(item.target_weight_pct || 0).toFixed(1)}%</span></strong>
            <small>${escapeHtml(rep.symbol ? symbolDisplayName(rep.symbol, rep) : "대표 종목 대기")} · ${escapeHtml(item.why || "")}</small>
          </div>
        `;
      }).join("") + `<div class="sector-committee-list-item cash"><strong>현금 <span>${Number(report.cash_weight_pct || 0).toFixed(1)}%</span></strong><small>시장 국면과 리스크에 따라 자동 조절</small></div>`
      : `<div class="sector-committee-list-item">포트폴리오 초안 대기</div>`;
  }

  const votesNode = el("#sectorCommitteeVotes");
  if (votesNode) {
    const voteRows = [];
    sectors.slice(0, 3).forEach((sector) => {
      const votes = sector.votes || {};
      [...(Array.isArray(votes.pros) ? votes.pros.slice(0, 1) : []), ...(Array.isArray(votes.cons) ? votes.cons.slice(0, 2) : [])]
        .forEach((vote) => voteRows.push({ sector: sector.name, ...vote }));
    });
    const comparisons = Array.isArray(report.comparison) ? report.comparison.slice(0, 3) : [];
    votesNode.innerHTML = `
      <div class="sector-committee-list-item ${guardClass}">
        <strong>편중 감시 <span>${escapeHtml(guardStatus)}</span></strong>
        <small>${escapeHtml(guard.message || "-")}</small>
      </div>
      ${voteRows.map((vote) => `
        <div class="sector-committee-list-item">
          <strong>${escapeHtml(vote.agent || "-")} <span>${escapeHtml(vote.stance || "-")}</span></strong>
          <small>${escapeHtml(vote.sector || "-")} · ${escapeHtml(vote.reason || "")}</small>
        </div>
      `).join("")}
      ${comparisons.map((item) => `
        <div class="sector-committee-list-item compare">
          <strong>${escapeHtml(item.sector || "-")} <span>${escapeHtml(item.change || "-")}</span></strong>
          <small>${escapeHtml(item.reason || "")}</small>
        </div>
      `).join("")}
    `;
  }
}

async function loadSectorCommittee(force = false) {
  setText("sectorCommitteeState", force ? "회의 중" : "조회 중");
  try {
    const response = await fetch(force ? "/api/agent/sector-committee?force=1" : "/api/agent/sector-committee");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "업종 투자위원회 조회 실패");
    renderSectorCommittee(result);
    if (force) {
      const chair = result.chair || {};
      addLog(`업종 투자위원회 완료: ${chair.approval || "-"} · 현금 ${Number(result.cash_weight_pct || 0).toFixed(1)}%`);
    }
  } catch (error) {
    const fallback = state.lastSectorCommittee;
    if (fallback && Array.isArray(fallback.sector_rankings)) {
      setText("sectorCommitteeState", "캐시 유지");
      addLog(`업종 투자위원회 실패, 마지막 결과 유지: ${error.message}`);
      return;
    }
    setText("sectorCommitteeState", "실패");
    addLog(`업종 투자위원회 실패: ${error.message}`);
  }
}

function renderOpportunities(result = {}) {
  setText("opportunityState", result.refreshing ? "캐시 · 갱신 중" : result.cached ? "캐시" : "최신");
  setText("opportunityMethod", result.method || "섹터별 추천 카드");
  setText("opportunitySafety", result.refresh_message || result.safety || "상승여력은 확정 전망이 아니라 연구용 가설입니다.");
  const topNode = el("#opportunityTopCards");
  const topCards = Array.isArray(result.top_cards) ? result.top_cards : [];
  if (topNode) {
    topNode.innerHTML = topCards.length
      ? topCards.slice(0, 6).map((card) => renderOpportunityCard(card, true)).join("")
      : `<div class="opportunity-empty">추천 카드 대기</div>`;
  }
  const sectorNode = el("#opportunitySectors");
  const sectors = Array.isArray(result.sectors) ? result.sectors : [];
  if (!sectorNode) return;
  sectorNode.innerHTML = sectors.length
    ? sectors.map((sector) => {
      const score = Number(sector.sector_news_score || 0);
      const klass = score > 0 ? "up" : score < 0 ? "down" : "flat";
      const cards = Array.isArray(sector.cards) ? sector.cards.slice(0, 4) : [];
      const notes = Array.isArray(sector.learning_notes) ? sector.learning_notes.slice(0, 3) : [];
      const sectorLinks = Array.isArray(sector.news_links) ? sector.news_links.slice(0, 3) : [];
      return `
        <section class="opportunity-sector">
          <div class="opportunity-sector-head">
            <div>
              <strong>${escapeHtml(sector.name || "-")}</strong>
              <small>${escapeHtml(sector.summary || "")}</small>
            </div>
            <span class="${klass}">${escapeHtml(sector.stance || "-")} · 섹터 ${score >= 0 ? "+" : ""}${score.toFixed(0)} · 후보평균 ${Number(sector.avg_candidate_score || 0).toFixed(1)}</span>
          </div>
          <div class="opportunity-notes">
            ${notes.map((item) => `<small>${escapeHtml(replaceSymbolCodesInText(item))}</small>`).join("")}
          </div>
          ${sectorLinks.length ? `<div class="opportunity-sector-links">${sectorLinks.map((item) => {
            const title = replaceSymbolCodesInText(item.title || "");
            return `<a href="${escapeHtml(item.link || "#")}" target="_blank" rel="noreferrer">${escapeHtml(item.source || "섹터기사")} · ${escapeHtml(String(title).slice(0, 56))}</a>`;
          }).join("")}</div>` : ""}
          <div class="opportunity-card-grid">
            ${cards.length ? cards.map((card) => renderOpportunityCard(card)).join("") : `<div class="opportunity-empty">핵심 종목 데이터 대기</div>`}
          </div>
        </section>
      `;
    }).join("")
    : `<div class="opportunity-empty">섹터 추천 카드 대기</div>`;
}

async function loadOpportunities(force = false) {
  setText("opportunityState", force ? "갱신 중" : "조회 중");
  try {
    const response = await fetch(force ? "/api/agent/opportunities?force=1" : "/api/agent/opportunities");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "추천 카드 조회 실패");
    renderOpportunities(result);
    if (force) addLog(result.refreshing ? "AI 섹터 추천 카드: 캐시를 먼저 표시하고 백그라운드 갱신을 시작했습니다." : `AI 섹터 추천 카드 갱신: ${(result.sectors || []).length}개 섹터`);
  } catch (error) {
    setText("opportunityState", "실패");
    addLog(`AI 섹터 추천 카드 실패: ${error.message}`);
  }
}

function renderTossRadar(radar = {}) {
  const node = el("#tossRadarRows");
  if (!node) return;
  const rows = Array.isArray(radar.items) ? radar.items : [];
  node.innerHTML = rows.length
    ? rows.slice(0, 8).map((row) => {
      const signal = row.signal || {};
      const delta = Number(signal.score_delta || 0);
      const klass = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
      return `
        <div class="radar-item">
          <strong>${escapeHtml(symbolDisplayName(row.symbol, row))}</strong>
          <span class="${klass}">${signal.label || (row.ok ? "중립" : "조회 실패")} · ${delta >= 0 ? "+" : ""}${delta.toFixed(1)}</span>
          <small>현재가 ${money0(row.price)} · 등락 ${pct(row.change_pct || 0)} · 거래량 ${money0(row.volume)} · RSI ${row.rsi14 ?? "-"}</small>
          <small>${signal.detail || row.message || "공개 시세 확인 대기"}</small>
        </div>
      `;
    }).join("")
    : `<div class="radar-item"><strong>공개 시세 대기</strong><small>국내 6자리 종목은 토스 공개 데이터를 읽기전용 보조 신호로 확인합니다.</small></div>`;
}

async function loadScreener(force = false) {
  setText("screenerState", force ? "발굴 요청" : "조회 중");
  try {
    const response = await fetch(force ? "/api/agent/screener?force=1" : "/api/agent/screener");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "후보발굴 조회 실패");
    state.lastScreenerResult = result;
    const top = result.top || {};
    const stateLabel = result.refreshing ? "갱신 중" : result.quick_snapshot ? "빠른 후보" : result.cached ? "캐시" : result.ok === false ? "캐시 유지" : "최신";
    setText("screenerState", stateLabel);
    setText("screenerTopSymbol", top.symbol ? symbolDisplayName(top.symbol, top) : "-");
    if (top.symbol && el("#dossierSymbol") && !el("#dossierSymbol").dataset.touched) el("#dossierSymbol").value = symbolDisplayName(top.symbol, top);
    setText("screenerTopScore", top.score !== undefined ? Number(top.score || 0).toFixed(1) : "-");
    setText("screenerTargetCount", `${result.target_count || 0}개`);
    setText("screenerMethod", result.method || "-");
    renderScreenerRows(result.candidates || []);
    const sectorPlan = result.sector_committee_plan || {};
    const sectorChair = sectorPlan.chairman_conclusion || {};
    const alternativeWatch = Array.isArray(sectorPlan.alternative_watchlist) ? sectorPlan.alternative_watchlist : [];
    const alternativeLine = alternativeWatch.length
      ? alternativeWatch.slice(0, 3).map((row) => `${symbolDisplayName(row.symbol, row)}(${row.sector || "-"})`).join(" · ")
      : "";
    const actions = [
      ...(result.refresh_message ? [result.refresh_message] : []),
      ...(result.error ? [`후보발굴 오류: ${result.error}`] : []),
      ...(sectorChair.summary ? [`업종 투자위원회: ${sectorChair.summary}`] : []),
      ...(alternativeLine ? [`대체 업종 관찰: ${alternativeLine}`] : []),
      ...(result.next_actions || []),
    ];
    el("#screenerActions").innerHTML = actions.length
      ? actions.slice(0, 6).map((item) => `<div class="screener-action">${escapeHtml(replaceSymbolCodesInText(item))}</div>`).join("")
      : `<div class="screener-action">다음 작업 대기</div>`;
    renderDaytradeActionCards();
    if (force) {
      const message = result.refreshing
        ? `AI 후보발굴 백그라운드 갱신 중: 현재 화면은 ${stateLabel}`
        : `AI 후보발굴 완료: ${top.symbol ? symbolDisplayName(top.symbol, top) : "-"} 점수 ${top.score || "-"}`;
      addLog(message);
    }
  } catch (error) {
    const fallback = state.lastScreenerResult;
    if (fallback && Array.isArray(fallback.candidates)) {
      setText("screenerState", "캐시 유지");
      renderScreenerRows(fallback.candidates || []);
      addLog(`AI 후보발굴 실패, 마지막 정상 후보 유지: ${error.message}`);
      return;
    }
    setText("screenerState", "실패");
    addLog(`AI 후보 발굴 실패: ${error.message}`);
  }
}

function renderDossierList(selector, rows = [], emptyText = "대기") {
  const node = el(selector);
  if (!node) return;
  node.innerHTML = rows.length
    ? rows.slice(0, 8).map((item) => `<div class="dossier-item">${escapeHtml(String(item || ""))}</div>`).join("")
    : `<div class="dossier-item">${escapeHtml(emptyText)}</div>`;
}

async function runDossier(symbolOverride = "") {
  const raw = String(symbolOverride || el("#dossierSymbol")?.value || "").trim();
  const symbol = resolveSymbolInput(raw);
  if (!symbol) return addLog("심층분석 종목명을 입력해주세요.");
  if (el("#dossierSymbol")) el("#dossierSymbol").value = symbolDisplayName(symbol);
  setText("dossierState", "분석 중");
  try {
    const response = await fetch(`/api/agent/dossier?force=1&symbol=${encodeURIComponent(symbol)}`);
    const dossier = await response.json();
    if (!response.ok) throw new Error(dossier.error || "심층 리포트 생성 실패");
    const score = dossier.scorecard || {};
    const financial = dossier.financial || {};
    const risks = dossier.risks || [];
    const dossierName = symbolDisplayName(dossier.symbol || symbol, dossier);
    setText("dossierState", "완료");
    setText("dossierTitle", dossierName);
    setText("dossierScore", score["종합점수"] !== undefined ? Number(score["종합점수"] || 0).toFixed(1) : "-");
    setText("dossierFinancial", `${financial.stance || "-"} · ${financial.score || 0}`);
    setText("dossierRisk", `${risks.length || 0}개`);
    setText("dossierVerdict", dossier.verdict || "-");
    setText("dossierNotePath", dossier.note_path ? `Obsidian 저장: ${dossier.note_path}` : "-");
    renderDossierList("#dossierThesis", dossier.thesis || [], "투자 가설 대기");
    renderDossierList("#dossierNext", dossier.next_research || [], "다음 조사 과제 대기");
    addLog(`AI 심층 리포트 완료: ${dossierName}`);
  } catch (error) {
    setText("dossierState", "실패");
    addLog(`AI 심층 리포트 실패: ${error.message}`);
  }
}

async function loadRadar(force = false) {
  setText("radarState", force ? "갱신 요청" : "조회 중");
  try {
    const response = await fetch(force ? "/api/agent/radar?force=1" : "/api/agent/radar");
    const radar = await response.json();
    if (!response.ok) throw new Error(radar.error || "뉴스/재무 레이더 조회 실패");
    setText("radarState", radar.refreshing ? "갱신 중" : radar.cached ? "캐시" : radar.ok === false ? "캐시 유지" : "최신");
    setText("radarGeneratedAt", `${radar.generated_at || "-"} · ${radar.safety || ""}`);
    renderNewsRadar(radar.news || []);
    renderFinancialRadar(radar.financials || []);
    renderTossRadar(radar.toss_public || {});
    renderRadarTasks([
      ...(radar.refresh_message ? [radar.refresh_message] : []),
      ...(radar.error ? [`레이더 오류: ${radar.error}`] : []),
      ...(radar.watch_tasks || []),
    ]);
    if (force) {
      addLog(radar.refreshing
        ? "뉴스/재무 레이더: 기존 결과를 먼저 표시하고 백그라운드 갱신을 시작했습니다."
        : `뉴스/재무 레이더 갱신: ${(radar.symbols || []).map((symbol) => symbolDisplayName(symbol)).join(", ")}`);
    }
  } catch (error) {
    setText("radarState", "실패");
    addLog(`뉴스/재무 레이더 실패: ${error.message}`);
  }
}

function renderSectorNews(report = {}) {
  const node = el("#sectorNewsRows");
  if (!node) return;
  const sectors = Array.isArray(report.sectors) ? report.sectors : [];
  node.innerHTML = sectors.length
    ? sectors.map((sector) => {
      const score = Number(sector.score || 0);
      const klass = score > 0 ? "up" : score < 0 ? "down" : "flat";
      const firstItems = (sector.items || []).slice(0, 2).map((item) => item.title).filter(Boolean).join(" / ");
      return `
        <div class="sector-card">
          <strong>${sector.name || "-"}</strong>
          <span class="${klass}">${sector.stance || "-"} · 점수 ${score}</span>
          <small>${sector.summary || firstItems || "뉴스 요약 대기"}</small>
          <small>긍정 ${sector.positive_count || 0} · 위험 ${sector.risk_count || 0} · ${sector.message || ""}</small>
        </div>
      `;
    }).join("")
    : `<div class="sector-card"><strong>섹터뉴스 대기</strong><small>수집 버튼을 누르면 섹터별 기사 제목을 정리하고 기록합니다.</small></div>`;
  setText("sectorNewsNote", report.note_path ? `기록: ${report.note_path}` : (report.safety || "-"));
}

async function loadSectorNews(force = false) {
  setText("sectorNewsState", force ? "수집/기록 중" : "조회 중");
  try {
    const response = await fetch(force ? "/api/agent/sector-news/run" : "/api/agent/sector-news", {
      method: force ? "POST" : "GET",
      headers: force ? { "Content-Type": "application/json" } : undefined,
      body: force ? "{}" : undefined,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "섹터뉴스 조회 실패");
    state.sectorNews = result;
    setText("sectorNewsState", result.cached ? "캐시" : "최신 기록");
    renderSectorNews(result);
    if (force) addLog(`섹터뉴스 수집/기록 완료: ${(result.sectors || []).length}개 섹터`);
  } catch (error) {
    setText("sectorNewsState", "실패");
    addLog(`섹터뉴스 조회 실패: ${error.message}`);
  }
}

function capitalHistoryStatusLabel(status = "info") {
  return {
    start: "시작",
    running: "진행",
    success: "완료",
    error: "실패",
    info: "기록",
  }[status] || "기록";
}

function renderCapitalActionHistory() {
  const node = el("#capitalActionHistory");
  if (!node) return;
  const rows = Array.isArray(state.capitalActionHistory) ? state.capitalActionHistory : [];
  node.innerHTML = rows.length
    ? rows.map((row) => `
      <div class="capital-history-row ${escapeHtml(row.status || "info")}">
        <b>${escapeHtml(row.title || "작업 기록")}</b>
        <span>${escapeHtml(row.detail || "-")}</span>
        <small>${escapeHtml(capitalHistoryStatusLabel(row.status))} · ${escapeHtml(row.time || "")}</small>
      </div>
    `).join("")
    : `<div class="capital-history-empty"><b>실행 이력 대기</b><span>버튼을 누르면 시작, 완료, 실패가 시간순으로 남고 최근 7개는 새로고침 후에도 보존됩니다.</span></div>`;
}

function saveCapitalActionHistory() {
  try {
    localStorage.setItem(
      CAPITAL_ACTION_HISTORY_STORAGE_KEY,
      JSON.stringify((state.capitalActionHistory || []).slice(0, 7)),
    );
  } catch (_) {}
}

function pushCapitalActionHistory(status = "info", title = "작업 기록", detail = "") {
  const row = {
    status,
    title,
    detail,
    time: new Date().toLocaleTimeString("ko-KR", { hour12: false }),
  };
  state.capitalActionHistory = [row, ...(state.capitalActionHistory || [])].slice(0, 7);
  saveCapitalActionHistory();
  renderCapitalActionHistory();
}

function renderCapitalActionPanel(mode = "idle", result = {}, meta = {}) {
  const lastNode = el("#capitalLastAction");
  const resultNode = el("#capitalActionResult");
  const deltaNode = el("#capitalRunDelta");
  if (!lastNode || !resultNode || !deltaNode) return;
  const before = meta.before || {};
  const elapsed = Number(meta.elapsed_seconds || 0);
  const beforeMultiple = Number(before.achieved_multiple || 0);
  const afterMultiple = Number(result.achieved_multiple || 0);
  const beforeProgress = Number(before.progress_pct || 0);
  const afterProgress = Number(result.progress_pct || 0);
  const multipleDelta = afterMultiple - beforeMultiple;
  const progressDelta = afterProgress - beforeProgress;
  const idChanged = before.id && result.id && before.id !== result.id;
  const generatedAt = result.generated_at ? formatDateTimeShort(result.generated_at) : "기록 없음";
  const auto = meta.auto || {};
  const activePhaseId = (meta.job || {}).phase_id || (meta.job || {}).selected_phase || meta.phase_id || state.activeCapitalPhaseTraining || "";
  const isPhaseResult = Boolean(result.phase_only || (meta.job || {}).mode === "phase" || meta.action === "phase" || activePhaseId);
  const activePhaseLabel = activePhaseId ? capitalPhaseDisplayName(activePhaseId) : "";
  const modeLabel = {
    loading: "최근 결과 조회 중",
    loaded: "최근 결과 조회 완료",
    running: isPhaseResult ? "구간별 훈련 실행 중" : "새 100억 프로젝트 실행 중",
    completed: isPhaseResult ? "구간별 훈련 완료" : "새 100억 프로젝트 실행 완료",
    error: "작업 실패",
    idle: "대기",
  }[mode] || mode;
  const activeAction = isPhaseResult
    ? "phase"
    : mode === "loading" || mode === "loaded" || (mode === "error" && meta.force === false)
      ? "refresh"
      : mode === "running" || mode === "completed" || meta.force
        ? "run"
        : "";
  document.querySelectorAll("[data-capital-action-card]").forEach((card) => {
    const isActive = Boolean(activeAction) && card.dataset.capitalActionCard === activeAction;
    card.classList.toggle("is-active", isActive);
    card.classList.toggle("is-running", isActive && mode === "running");
    card.classList.toggle("is-error", isActive && mode === "error");
  });
  lastNode.textContent = `${modeLabel} · ${new Date().toLocaleTimeString("ko-KR", { hour12: false })}`;
  if (mode === "loading") {
    resultNode.textContent = "저장된 최신 결과만 불러오는 중입니다.";
    deltaNode.textContent = "새 계산은 돌리지 않습니다. 마지막 기록 ID와 숫자만 확인합니다.";
    return;
  }
  if (mode === "running") {
    const job = meta.job || {};
    const jobProgress = Math.max(0, Math.min(Number(job.progress_pct || 0), 100));
    const phaseIndex = Number(job.phase_index || 0);
    const phaseCount = Number(job.phase_count || 0);
    const baseLabel = job.current_label || (job.mode === "phase" || activePhaseId ? "선택 구간 훈련 준비 중" : "전체 구간 훈련 준비 중");
    const label = activePhaseLabel && !String(baseLabel).includes(activePhaseLabel)
      ? `${baseLabel} · ${activePhaseLabel}`
      : baseLabel;
    const hours = Number(job.compressed_training_hours || 0).toLocaleString();
    const trades = Number(job.trade_count || 0).toLocaleString();
    resultNode.textContent = `${job.mode === "phase" ? "선택 구간 훈련" : "새 과거장 훈련"} 실행 중 · ${jobProgress.toFixed(1)}%`;
    deltaNode.textContent = `${label} · ${phaseIndex || 0}/${phaseCount || "-"}구간 · 압축훈련 ${hours}시간 · 매매 ${trades}회`;
    return;
  }
  if (mode === "error") {
    resultNode.textContent = "작업 실패";
    deltaNode.textContent = meta.error || "오류 내용을 확인해야 합니다.";
    return;
  }
  const viewOnly = auto.status === "VIEW_ONLY" || meta.force === false;
  resultNode.textContent = viewOnly
    ? `조회 완료 · 최신 기록 ${result.id || "-"} · ${generatedAt}`
    : isPhaseResult
      ? `구간 훈련 완료 · ${activePhaseLabel || capitalPhaseDisplayName(result.selected_phase || ((result.phases || [])[0] || {}).phase || "") || "-"} · ${generatedAt}`
      : `실행 완료 · ${idChanged ? "새 기록 생성" : "기록 갱신 확인"} · ${result.id || "-"} · ${generatedAt}`;
  const deltaText = before.id
    ? `이전 대비 배수 ${multipleDelta >= 0 ? "+" : ""}${multipleDelta.toFixed(4)}배 · 진행률 ${progressDelta >= 0 ? "+" : ""}${progressDelta.toFixed(4)}%p`
    : "비교할 이전 화면 기록이 없어 최신 결과만 표시했습니다.";
  const actionText = viewOnly
    ? "최근 결과 보기는 저장된 결과만 확인합니다. 새 계산이 필요하면 오른쪽 실행 버튼을 누르면 됩니다."
    : isPhaseResult
      ? `선택 구간만 ${elapsed.toFixed(1)}초 동안 다시 훈련했고, 구간별 훈련 기록에 저장됐습니다.`
      : `새 실행은 ${elapsed.toFixed(1)}초 걸렸고, 장기기억/프로젝트 기록에 저장됐습니다.`;
  deltaNode.textContent = `${deltaText} · ${actionText}`;
}

function setCapitalButtonState(button, busy = false, active = false, busyLabel = "") {
  if (!button) return;
  if (!button.dataset.defaultText) button.dataset.defaultText = button.textContent.trim();
  button.disabled = busy;
  button.classList.toggle("is-busy", busy && active);
  button.textContent = busy && active ? busyLabel : button.dataset.defaultText;
}

function capitalPhaseDisplayName(phaseId = "") {
  const key = canonicalCapitalPhaseKey(phaseId);
  const scenario = (state.capitalScenarioCatalog || []).find((item) => canonicalCapitalPhaseKey(item.phase) === key);
  return scenario?.label || phaseId || "";
}

function setCapitalButtonsBusy(busy = false, activeAction = "", activePhase = "") {
  const refresh = el("#refreshCapitalChallenge");
  const run = el("#runCapitalChallenge");
  setCapitalButtonState(refresh, busy, activeAction === "refresh", "최근 결과 조회 중...");
  setCapitalButtonState(run, busy, activeAction === "run", "100억 프로젝트 실행 중...");
  const hasResult = Boolean(state.lastCapitalChallenge?.id || state.lastCapitalChallenge?.generated_at);
  ["#copyCapitalSummary", "#downloadCapitalSummary"].forEach((selector) => {
    const button = el(selector);
    if (button) button.disabled = busy || !hasResult;
  });
  document.querySelectorAll("[data-capital-phase-train]").forEach((button) => {
    const phase = String(button.dataset.capitalPhaseTrain || "");
    const active = activeAction === "phase" && (!activePhase || activePhase === phase);
    setCapitalButtonState(button, busy, active, "이 구간 훈련 중...");
  });
  if (!busy) updateCapitalSummaryCopyButton();
}

function scheduleCapitalChallengeJobPoll(before = {}, startedAt = performance.now()) {
  if (state.capitalChallengeJobTimer) {
    clearTimeout(state.capitalChallengeJobTimer);
    state.capitalChallengeJobTimer = null;
  }
  state.capitalChallengeJobTimer = setTimeout(() => pollCapitalChallengeJob(before, startedAt), 5000);
}

async function pollCapitalChallengeJob(before = {}, startedAt = performance.now()) {
  state.capitalChallengeJobTimer = null;
  try {
    const response = await fetch("/api/agent/capital-challenge/job");
    const job = await response.json();
    if (Array.isArray(job.scenarios)) {
      state.capitalScenarioCatalog = job.scenarios;
    }
    if (!response.ok) throw new Error(job.error || "100억 프로젝트 작업 상태 조회 실패");
    if (job.running || job.status === "RUNNING") {
      const runningPhase = job.phase_id || job.selected_phase || state.activeCapitalPhaseTraining || "";
      setCapitalButtonsBusy(true, job.mode === "phase" || runningPhase ? "phase" : "run", runningPhase);
      setText("capitalState", `백그라운드 실행 중 · ${Number(job.progress_pct || 0).toFixed(1)}% · ${formatDateTimeShort(job.started_at)}`);
      renderCapitalActionPanel("running", job.latest || state.lastCapitalChallenge || {}, { before, force: true, job });
      scheduleCapitalChallengeJobPoll(before, startedAt);
      return;
    }
    const result = job.result || job.latest || {};
    if (result && result.phase_only) {
      renderCapitalPhaseTrainingResult(result);
    } else if (result && Object.keys(result).length) {
      renderCapitalChallenge(result);
    }
    const elapsed = (performance.now() - startedAt) / 1000;
    renderCapitalActionPanel(job.status === "ERROR" ? "error" : "completed", result, {
      before,
      force: true,
      elapsed_seconds: elapsed,
      error: job.error || job.message,
      action: result.phase_only || state.activeCapitalPhaseTraining ? "phase" : "",
      phase_id: result.selected_phase || state.activeCapitalPhaseTraining,
    });
    pushCapitalActionHistory(
      job.status === "ERROR" ? "error" : "success",
      job.status === "ERROR"
        ? "백그라운드 훈련 실패"
        : result.phase_only
          ? "구간별 훈련 완료"
          : "100억 프로젝트 완료",
      job.status === "ERROR"
        ? (job.error || job.message || "작업 상태를 확인해야 합니다.")
        : result.phase_only
          ? `${(result.phases || [])[0]?.label || result.selected_phase || "-"} · ${elapsed.toFixed(1)}초`
          : `진행률 ${Number(result.progress_pct || 0).toFixed(4)}% · 달성 ${Number(result.achieved_multiple || 0).toFixed(4)}배`,
    );
    setCapitalButtonsBusy(false);
    state.activeCapitalPhaseTraining = "";
    addLog(job.status === "ERROR"
      ? `100억 프로젝트 백그라운드 실패: ${job.error || job.message}`
      : result.phase_only
        ? `구간별 훈련 완료: ${(result.phases || [])[0]?.label || result.selected_phase || "-"}`
        : `100억 프로젝트 백그라운드 완료: ${Number(result.achieved_multiple || 0).toFixed(4)}배 / 진행률 ${Number(result.progress_pct || 0).toFixed(4)}%`);
  } catch (error) {
    setText("capitalState", "작업 상태 확인 실패");
    renderCapitalActionPanel("error", {}, { before, force: true, error: error.message, action: state.activeCapitalPhaseTraining ? "phase" : "", phase_id: state.activeCapitalPhaseTraining });
    pushCapitalActionHistory("error", "작업 상태 확인 실패", error.message);
    setCapitalButtonsBusy(false);
    state.activeCapitalPhaseTraining = "";
    addLog(`100억 프로젝트 작업 상태 확인 실패: ${error.message}`);
  }
}

function capitalTradeDisplayName(trade = {}) {
  return trade.display_name
    || pointInTimeDisplayName(trade.symbol, trade.entry_date || trade.date || trade.name_as_of_date, trade)
    || trade.name
    || trade.symbol
    || "-";
}

function renderCapitalTradeTopRows(trades = [], limit = 10, emptyTitle = "TOP10 대기", emptyText = "구간 훈련을 다시 돌리면 수익률 상위 매매가 표시됩니다.") {
  const rows = Array.isArray(trades) ? trades.slice(0, limit) : [];
  if (!rows.length) {
    return `<div class="capital-trade-row empty"><b>${escapeHtml(emptyTitle)}</b><span>${escapeHtml(emptyText)}</span></div>`;
  }
  return rows.map((trade, index) => {
    const pnl = Number(trade.pnl_pct || 0);
    const tradeName = capitalTradeDisplayName(trade);
    return `
    <div class="capital-trade-row ${pnl < 0 ? "loss" : "gain"}">
      <b>${index + 1}. ${escapeHtml(tradeName || trade.name || trade.symbol || "-")} <i>${pnl.toFixed(2)}%</i></b>
      <span>매수: ${escapeHtml(trade.entry_reason || "-")}</span>
      <span>매도: ${escapeHtml(trade.exit_reason || "-")}</span>
      <small>${escapeHtml(trade.entry_date || "-")} → ${escapeHtml(trade.exit_date || "-")} · ${Number(trade.holding_days || 0).toLocaleString()}일 보유</small>
    </div>
  `;
  }).join("");
}

function capitalPhaseBottomTrades(phase = {}, limit = 3) {
  const trades = Array.isArray(phase.trade_journal_bottom10) && phase.trade_journal_bottom10.length
    ? phase.trade_journal_bottom10
    : Array.isArray(phase.bottom_trades) && phase.bottom_trades.length
      ? phase.bottom_trades
      : Array.isArray(phase.trade_journal_sample) ? phase.trade_journal_sample : [];
  return trades
    .filter((trade) => trade && Object.keys(trade).length && Number(trade.pnl_pct || 0) < 0)
    .sort((a, b) => Number(a.pnl_pct || 0) - Number(b.pnl_pct || 0))
    .slice(0, limit);
}

function capitalPhaseStartDate(phase = {}) {
  const period = String(phase.period || phase.start || "");
  const match = period.match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : "";
}

function capitalPhaseSymbolLabelText(phase = {}, limit = 8) {
  const labels = Array.isArray(phase.symbol_labels) && phase.symbol_labels.length
    ? phase.symbol_labels.map((row) => row.display_name || row.name || row.symbol).filter(Boolean)
    : (Array.isArray(phase.symbols) ? phase.symbols : []).map((symbol) => pointInTimeDisplayName(symbol, capitalPhaseStartDate(phase)));
  return labels.slice(0, limit).join(" · ");
}

function capitalPhasePointInTimeWarning(phase = {}) {
  if (phase.point_in_time_warning) return String(phase.point_in_time_warning);
  const labels = capitalPhaseSymbolLabelText(phase, 12);
  return labels.includes("(현 ") ? "시점명 보정 표시 중입니다. 상장/상폐/상호변경 전체 유니버스 검증은 추가로 필요합니다." : "";
}

function canonicalCapitalPhaseKey(value = "") {
  const key = String(value || "").trim().toUpperCase();
  return {
    "10Y-1": "TREND-2016",
    "10Y-2": "WEAK-2018",
    "1": "GROWTH-2020",
    "2": "WEAK-2022",
    "3": "LEADER-2024",
  }[key] || key;
}

function mergedCapitalPhases(result = {}) {
  const actual = Array.isArray(result.phases) ? result.phases : [];
  const scenarios = Array.isArray(result.scenarios) && result.scenarios.length
    ? result.scenarios
    : state.capitalScenarioCatalog;
  if (!scenarios.length) return actual;
  const hasPre2016Actual = actual.some((phase) => {
    const period = String(phase.period || "");
    const year = Number((period.match(/\d{4}/) || [])[0] || 9999);
    return year < 2016;
  });
  if (hasPre2016Actual) return actual;
  const actualByKey = new Map();
  actual.forEach((phase) => {
    actualByKey.set(canonicalCapitalPhaseKey(phase.phase), phase);
  });
  return scenarios.map((scenario) => {
    const key = canonicalCapitalPhaseKey(scenario.phase);
    const matched = actualByKey.get(key);
    if (matched) return { ...scenario, ...matched, phase: scenario.phase, legacy_phase: matched.phase };
    return {
      ...scenario,
      status: "PENDING",
      return_pct: null,
      final_equity: null,
      max_drawdown_pct: null,
      trade_count: 0,
      win_rate_pct: null,
      compressed_training_hours: 0,
      training_run_label: "아직 미훈련",
      lesson: "아직 이 2000년대 구간은 새 전체 실행 또는 구간별 훈련 전입니다.",
      trade_journal_top10: [],
    };
  });
}

function renderCapitalPhaseTrainingResult(result = {}) {
  const node = el("#capitalPhaseTrainingResult");
  if (!node) return;
  const phase = Array.isArray(result.phases) ? result.phases[0] || {} : {};
  if (!phase || !Object.keys(phase).length) {
    node.innerHTML = "구간별 카드의 ‘이 구간만 다시 훈련’을 누르면 최신 결과가 여기에 따로 표시됩니다.";
    return;
  }
  state.lastCapitalPhaseTraining = result;
  const returnPct = Number(phase.return_pct || 0);
  const status = phase.status === "ERROR" ? "실패" : "완료";
  const journalPath = phase.trade_journal_markdown_path || phase.trade_journal_path || "";
  node.innerHTML = `
    <div>
      <strong>${escapeHtml(phase.label || result.selected_phase || "선택 구간")}</strong>
      <span>${escapeHtml(status)} · ${escapeHtml(phase.period || "-")} · ${escapeHtml(phase.regime || "구간 훈련")}</span>
    </div>
    <div class="capital-phase-training-metrics">
      <b class="${returnPct >= 0 ? "up" : "down"}">${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%</b><small>수익률</small>
      <b>${money0(phase.final_equity || result.final_equity || 0)}원</b><small>최종금</small>
      <b>${Number(phase.max_drawdown_pct || 0).toFixed(2)}%</b><small>MDD</small>
      <b>${Number(phase.compressed_training_hours || 0).toLocaleString()}시간</b><small>압축훈련</small>
      <b>${Number(phase.trade_count || 0).toLocaleString()}회</b><small>매매</small>
    </div>
    <p>${escapeHtml(phase.lesson || phase.error || "구간별 훈련 결과를 기록했습니다.")}</p>
    <div class="capital-journal-path">${journalPath ? `전체 매매일지: ${escapeHtml(journalPath)}` : "전체 매매일지는 다음 훈련부터 자동 저장됩니다."}</div>
    <div class="capital-trade-top10">
      <strong>수익률 TOP 10</strong>
      ${renderCapitalTradeTopRows(phase.trade_journal_top10 || phase.top_trades || [], 10)}
    </div>
  `;
}

function capitalScoreReadout(result = {}) {
  if (!result || !Object.keys(result).length) {
    return "최근 결과를 불러오면 현재 위치와 다음 보완 방향을 한 줄로 읽어드립니다.";
  }
  const multiple = Number(result.achieved_multiple || 0);
  const remaining = Number(result.remaining_multiple || 0);
  const mdd = Math.abs(Number(result.worst_max_drawdown_pct || 0));
  const progress = Number(result.progress_pct || 0);
  const mddLabel = mdd >= 50 ? "낙폭 위험" : mdd >= 30 ? "낙폭 주의" : "낙폭 관리권";
  let next = "상위 구간 매매일지와 실패 구간을 복기하면 됩니다.";
  if (progress >= 100) next = "목표 달성 기록이므로 재현성과 위험 제한을 먼저 검증해야 합니다.";
  else if (mdd >= 50) next = "다음 훈련은 수익 확대보다 낙폭 방어 규칙을 우선해야 합니다.";
  else if (multiple < 2) next = "전략 후보 탐색기와 구간별 반복훈련으로 성장 엔진을 더 찾아야 합니다.";
  else if (remaining > 100) next = "목표까지 거리가 커서 주도장 포착 전략과 자금 회전 실험이 더 필요합니다.";
  return `현재 ${multiple.toFixed(4)}배, 목표까지 ${remaining.toFixed(2)}배 남았습니다. MDD ${mdd.toFixed(2)}%로 ${mddLabel}이며, ${next}`;
}

function updateCapitalSummaryCopyButton() {
  const result = state.lastCapitalChallenge || {};
  const hasResult = Boolean(result.id || result.generated_at);
  const recordLabel = result.id || "최신 기록";
  const generatedLabel = result.generated_at ? formatDateTimeShort(result.generated_at) : "생성시각 없음";
  const fileName = hasResult ? capitalSummaryFileName(result) : "";
  const summaryHint = el("#capitalSummaryHint");
  if (summaryHint) {
    const phaseCount = mergedCapitalPhases(result).length;
    const topTradeCount = capitalSummaryTopTrades(result, 10).length;
    const lossTradeCount = capitalSummaryLossTrades(result, 10).length;
    summaryHint.textContent = hasResult
      ? `요약 가능 · ${recordLabel} · ${generatedLabel} · 구간 ${phaseCount.toLocaleString()}개, TOP매매 ${topTradeCount}개, 손실매매 ${lossTradeCount}개, 재훈련 4개, 교훈 ${(result.lessons || []).length || 0}개, 다음 과제 ${(result.next_tasks || []).length || 0}개 포함 · 저장명 ${fileName}`
      : "요약에는 달성 배수, 진행률, MDD, 구간별 결과, 수익/손실 매매, 재훈련 체크리스트, 교훈, 다음 과제가 포함됩니다.";
  }
  const copyButton = el("#copyCapitalSummary");
  if (copyButton) {
    copyButton.disabled = !hasResult;
    copyButton.title = hasResult
      ? `${recordLabel}(${generatedLabel}) 기준 요약을 Markdown 형식으로 클립보드에 복사합니다.`
      : "최근 결과를 불러오면 현재 100억 프로젝트 요약을 복사할 수 있습니다.";
  }
  const downloadButton = el("#downloadCapitalSummary");
  if (downloadButton) {
    downloadButton.disabled = !hasResult;
    downloadButton.title = hasResult
      ? `${recordLabel}(${generatedLabel}) 기준 요약을 ${fileName} 파일로 저장합니다.`
      : "최근 결과를 불러오면 현재 100억 프로젝트 요약을 저장할 수 있습니다.";
  }
}

function capitalChallengeSummaryText(result = state.lastCapitalChallenge || {}) {
  const phases = mergedCapitalPhases(result).slice(0, 8);
  const topTrades = capitalSummaryTopTrades(result, 10);
  const profitReview = capitalSummaryProfitReview(topTrades);
  const lossTrades = capitalSummaryLossTrades(result, 10);
  const lossReview = capitalSummaryLossReview(lossTrades);
  const retrainChecklist = capitalSummaryRetrainChecklist(topTrades, lossTrades);
  const tasks = Array.isArray(result.next_tasks) ? result.next_tasks.slice(0, 6) : [];
  const lessons = Array.isArray(result.lessons) ? result.lessons.slice(0, 5) : [];
  return [
    "# 코덱스스톡 100억 프로젝트 요약",
    "",
    `생성일: ${new Date().toLocaleString("ko-KR", { hour12: false })}`,
    `기록 ID: ${result.id || "-"}`,
    `기간 기준: ${result.start_year || "2000"}년부터 현재까지`,
    `시작금: ${money0(result.initial_cash || 0)}원`,
    `목표금: ${money0(result.target_cash || 0)}원`,
    `최종 평가금: ${money0(result.final_equity || 0)}원`,
    `달성 배수: ${Number(result.achieved_multiple || 0).toFixed(4)}배`,
    `목표 진행률: ${Number(result.progress_pct || 0).toFixed(4)}%`,
    `남은 필요 배수: ${Number(result.remaining_multiple || 0).toFixed(2)}배`,
    `최악 MDD: ${Number(result.worst_max_drawdown_pct || 0).toFixed(2)}%`,
    `총 매매: ${Number(result.total_trade_count || 0).toLocaleString()}회`,
    `압축훈련: ${Number(result.compressed_training_hours || 0).toLocaleString()}시간`,
    "",
    `요약 판단: ${capitalScoreReadout(result)}`,
    "",
    "## 구간별 요약",
    ...(phases.length
      ? phases.map((phase, index) => `${index + 1}. ${phase.label || phase.phase || "-"} · ${phase.period || "-"} · 수익률 ${phase.return_pct == null ? "훈련 전" : `${Number(phase.return_pct || 0).toFixed(2)}%`} · MDD ${phase.max_drawdown_pct == null ? "-" : `${Number(phase.max_drawdown_pct || 0).toFixed(2)}%`} · 매매 ${Number(phase.trade_count || 0).toLocaleString()}회`)
      : ["구간 결과 없음"]),
    "",
    "## 수익률 상위 매매 TOP10",
    ...(topTrades.length
      ? topTrades.map((trade, index) => `${index + 1}. ${capitalTradeDisplayName(trade)} · ${trade.phase_label || "구간 미상"} · 손익 ${Number(trade.pnl_pct || 0).toFixed(2)}% · ${trade.entry_date || "-"} → ${trade.exit_date || "-"} · 매수 ${trade.entry_reason || "-"} · 매도 ${trade.exit_reason || "-"}`)
      : ["수익률 상위 매매 기록 없음"]),
    "",
    "## 수익 복기 포인트",
    ...profitReview,
    "",
    "## 손실률 하위 매매 TOP10",
    ...(lossTrades.length
      ? lossTrades.map((trade, index) => `${index + 1}. ${capitalTradeDisplayName(trade)} · ${trade.phase_label || "구간 미상"} · 손익 ${Number(trade.pnl_pct || 0).toFixed(2)}% · ${trade.entry_date || "-"} → ${trade.exit_date || "-"} · 매수 ${trade.entry_reason || "-"} · 매도 ${trade.exit_reason || "-"}`)
      : ["손실 매매 기록 없음"]),
    "",
    "## 손실 복기 포인트",
    ...lossReview,
    "",
    "## 다음 재훈련 체크리스트",
    ...retrainChecklist,
    "",
    "## 교훈",
    ...(lessons.length ? lessons.map((lesson, index) => `${index + 1}. ${lesson}`) : ["아직 기록된 교훈 없음"]),
    "",
    "## 다음 개선 과제",
    ...(tasks.length ? tasks.map((task, index) => `${index + 1}. ${task}`) : ["아직 기록된 다음 과제 없음"]),
    "",
    "주의: 이 내용은 연구/모의훈련 기록이며 실전 수익을 보장하지 않습니다.",
  ].join("\n");
}

function capitalSummaryRetrainChecklist(topTrades = [], lossTrades = []) {
  const best = topTrades[0] || {};
  const worst = lossTrades[0] || {};
  const bestPhase = best.phase_label || "수익 구간 미상";
  const worstPhase = worst.phase_label || "손실 구간 미상";
  return [
    `살릴 조건: ${bestPhase}에서 큰 수익을 만든 진입 근거와 보유 규칙을 별도 전략 후보로 분리합니다.`,
    `버릴 조건: ${worstPhase}에서 반복 손실이 난 진입 근거, 추격 매수, 손절 지연 조건을 차단 규칙으로 만듭니다.`,
    `다시 돌릴 구간: ${bestPhase} 재현 훈련 1회, ${worstPhase} 방어 훈련 1회를 우선 실행합니다.`,
    "비교 기준: 같은 구간에서 기존 전략, 수익 조건 강화 전략, 손실 차단 전략을 나란히 돌려 MDD와 최종금을 비교합니다.",
  ];
}

function capitalSummaryProfitReview(topTrades = []) {
  if (!Array.isArray(topTrades) || !topTrades.length) {
    return ["수익 매매 표본이 없어 수익 복기 포인트를 계산하지 못했습니다."];
  }
  const best = topTrades[0] || {};
  const avgProfit = topTrades.reduce((sum, trade) => sum + Number(trade.pnl_pct || 0), 0) / topTrades.length;
  const phaseCounts = topTrades.reduce((acc, trade) => {
    const label = trade.phase_label || "구간 미상";
    acc[label] = (acc[label] || 0) + 1;
    return acc;
  }, {});
  const mostProfitPhase = Object.entries(phaseCounts).sort((a, b) => b[1] - a[1])[0] || ["구간 미상", 0];
  return [
    `가장 큰 수익: ${capitalTradeDisplayName(best)} ${Number(best.pnl_pct || 0).toFixed(2)}% · ${best.phase_label || "구간 미상"}`,
    `상위 매매 평균 수익률: ${avgProfit.toFixed(2)}% · 표본 ${topTrades.length.toLocaleString()}건`,
    `수익 집중 구간: ${mostProfitPhase[0]} ${Number(mostProfitPhase[1] || 0).toLocaleString()}건`,
    "다음 훈련 체크: 어떤 장세, 거래대금, 추세 조건에서 큰 수익이 반복됐는지 재현 규칙으로 분리합니다.",
  ];
}

function capitalSummaryLossReview(lossTrades = []) {
  if (!Array.isArray(lossTrades) || !lossTrades.length) {
    return ["손실 매매 표본이 없어 손실 복기 포인트를 계산하지 못했습니다."];
  }
  const worst = lossTrades[0] || {};
  const avgLoss = lossTrades.reduce((sum, trade) => sum + Number(trade.pnl_pct || 0), 0) / lossTrades.length;
  const phaseCounts = lossTrades.reduce((acc, trade) => {
    const label = trade.phase_label || "구간 미상";
    acc[label] = (acc[label] || 0) + 1;
    return acc;
  }, {});
  const mostLossPhase = Object.entries(phaseCounts).sort((a, b) => b[1] - a[1])[0] || ["구간 미상", 0];
  return [
    `가장 큰 손실: ${capitalTradeDisplayName(worst)} ${Number(worst.pnl_pct || 0).toFixed(2)}% · ${worst.phase_label || "구간 미상"}`,
    `평균 손실률: ${avgLoss.toFixed(2)}% · 표본 ${lossTrades.length.toLocaleString()}건`,
    `손실 집중 구간: ${mostLossPhase[0]} ${Number(mostLossPhase[1] || 0).toLocaleString()}건`,
    "다음 훈련 체크: 진입 근거가 약한 매매, 손절 지연, 약세장 반등 추격, 거래 표본 부족 구간을 우선 복기합니다.",
  ];
}

function capitalSummaryTopTrades(result = state.lastCapitalChallenge || {}, limit = 10) {
  const rows = [];
  mergedCapitalPhases(result).forEach((phase) => {
    const trades = Array.isArray(phase.trade_journal_top10) && phase.trade_journal_top10.length
      ? phase.trade_journal_top10
      : Array.isArray(phase.top_trades) ? phase.top_trades : [];
    trades.forEach((trade) => {
      rows.push({
        ...trade,
        phase_label: phase.label || phase.phase || trade.phase_label || "",
      });
    });
  });
  return rows
    .filter((trade) => trade && Object.keys(trade).length)
    .sort((a, b) => Number(b.pnl_pct || 0) - Number(a.pnl_pct || 0))
    .slice(0, limit);
}

function capitalSummaryLossTrades(result = state.lastCapitalChallenge || {}, limit = 10) {
  const rows = [];
  mergedCapitalPhases(result).forEach((phase) => {
    const trades = Array.isArray(phase.trade_journal_bottom10) && phase.trade_journal_bottom10.length
      ? phase.trade_journal_bottom10
      : Array.isArray(phase.bottom_trades) && phase.bottom_trades.length
        ? phase.bottom_trades
        : Array.isArray(phase.trade_journal_sample) && phase.trade_journal_sample.length
          ? phase.trade_journal_sample
          : Array.isArray(phase.top_trades) ? phase.top_trades : [];
    trades.forEach((trade) => {
      rows.push({
        ...trade,
        phase_label: phase.label || phase.phase || trade.phase_label || "",
      });
    });
  });
  return rows
    .filter((trade) => trade && Object.keys(trade).length && Number(trade.pnl_pct || 0) < 0)
    .sort((a, b) => Number(a.pnl_pct || 0) - Number(b.pnl_pct || 0))
    .slice(0, limit);
}

function capitalSummaryFileName(result = state.lastCapitalChallenge || {}) {
  const generated = result.generated_at || result.created_at || todayIso();
  const generatedToken = fileSafeToken(String(generated).slice(0, 19).replace("T", "-"), todayIso());
  const recordToken = fileSafeToken(result.id || result.training_iteration || "latest", "latest");
  return `codexstock-capital-summary-${generatedToken}-${recordToken}.md`;
}

function flashCapitalSummaryButton(selector, label, tone = "ok", duration = 1400) {
  const button = el(selector);
  if (!button) return;
  if (!button.dataset.defaultText) button.dataset.defaultText = button.textContent.trim();
  button.textContent = label;
  button.classList.add("is-busy");
  button.classList.toggle("is-flash-error", tone === "error");
  window.setTimeout(() => {
    button.textContent = button.dataset.defaultText || button.textContent;
    button.classList.remove("is-busy");
    button.classList.remove("is-flash-error");
    updateCapitalSummaryCopyButton();
  }, duration);
}

async function copyCapitalSummary() {
  try {
    if (!state.lastCapitalChallenge?.id && !state.lastCapitalChallenge?.generated_at) {
      throw new Error("복사할 100억 프로젝트 결과가 아직 없습니다.");
    }
    await copyTextToClipboard(capitalChallengeSummaryText());
    flashCapitalSummaryButton("#copyCapitalSummary", "복사 완료");
    updateCapitalSummaryCopyButton();
    setText("capitalActionResult", "요약 복사 완료");
    setText("capitalRunDelta", "현재 100억 프로젝트 결과, 구간별 요약, 수익/손실 복기 포인트, 재훈련 체크리스트, 상하위 매매 TOP10, 교훈, 다음 과제를 클립보드에 복사했습니다.");
    pushCapitalActionHistory("success", "결과 요약 복사 완료", "현재 100억 프로젝트 복기 요약을 클립보드에 복사했습니다.");
    addLog("100억 프로젝트 결과 요약 복사 완료");
  } catch (error) {
    flashCapitalSummaryButton("#copyCapitalSummary", "복사 실패", "error");
    setText("capitalActionResult", "요약 복사 실패");
    setText("capitalRunDelta", error.message);
    pushCapitalActionHistory("error", "결과 요약 복사 실패", error.message);
    addLog(`100억 프로젝트 결과 요약 복사 실패: ${error.message}`);
  }
}

async function downloadCapitalSummary() {
  try {
    if (!state.lastCapitalChallenge?.id && !state.lastCapitalChallenge?.generated_at) {
      throw new Error("저장할 100억 프로젝트 결과가 아직 없습니다.");
    }
    const blob = new Blob([capitalChallengeSummaryText()], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const fileName = capitalSummaryFileName();
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    flashCapitalSummaryButton("#downloadCapitalSummary", "저장 시작");
    updateCapitalSummaryCopyButton();
    setText("capitalActionResult", "요약 저장 시작");
    setText("capitalRunDelta", `현재 100억 프로젝트 결과, 수익/손실 복기 포인트, 재훈련 체크리스트, 상하위 매매 TOP10 포함 요약을 Markdown 파일로 저장했습니다. 파일명: ${fileName}`);
    pushCapitalActionHistory("success", "결과 요약 저장 시작", `Markdown 파일 저장을 시작했습니다. ${fileName}`);
    addLog(`100억 프로젝트 결과 요약 Markdown 저장 시작: ${fileName}`);
  } catch (error) {
    flashCapitalSummaryButton("#downloadCapitalSummary", "저장 실패", "error");
    setText("capitalActionResult", "요약 저장 실패");
    setText("capitalRunDelta", error.message);
    pushCapitalActionHistory("error", "결과 요약 저장 실패", error.message);
    addLog(`100억 프로젝트 결과 요약 저장 실패: ${error.message}`);
  }
}

function renderCapitalChallenge(result = {}) {
  state.lastCapitalChallenge = result;
  const progress = Number(result.progress_pct || 0);
  const ring = el("#capitalProgressRing");
  if (ring) ring.style.setProperty("--capital-progress", `${Math.max(0, Math.min(progress, 100))}%`);
  const autoState = result.auto_state || result.capital_challenge_state || {};
  const autoStatus = result.auto_status || autoState.last_status || "";
  setText(
    "capitalState",
    autoState.next_due_at
      ? `AI 자동 ${autoStatus || "대기"} · 다음 ${formatDateTimeShort(autoState.next_due_at)}`
      : result.cached ? "최근 기록" : result.generated_at ? "최신 실행" : "대기",
  );
  setText("capitalChallengeId", result.id || "-");
  setText("capitalProgress", `${progress.toFixed(4)}%`);
  setText("capitalInitial", `${money0(result.initial_cash || 0)}원`);
  setText("capitalTarget", `${money0(result.target_cash || 0)}원`);
  setText("capitalFinal", `${money0(result.final_equity || 0)}원`);
  setText("capitalMultiple", `${Number(result.achieved_multiple || 0).toFixed(4)}배`);
  setText("capitalRemaining", `${Number(result.remaining_multiple || 0).toFixed(2)}배`);
  setText("capitalMdd", `${Number(result.worst_max_drawdown_pct || 0).toFixed(2)}%`);
  setText("capitalScoreReadout", capitalScoreReadout(result));
  setText("capitalVerdict", result.verdict || "아직 챌린지를 실행하지 않았습니다.");
  const capitalRunLabel = result.training_iteration ? `${Number(result.training_iteration || 0).toLocaleString()}회차` : "기존 기록";
  const displayPhases = mergedCapitalPhases(result);
  const scenarioPrefix = displayPhases.some((phase) => String(phase.period || "").startsWith("2000-"))
    ? "2000년 구간표"
    : `${Number(result.phase_count || (Array.isArray(result.phases) ? result.phases.length : 0) || 0).toLocaleString()}구간`;
  setText(
    "capitalPhaseSummary",
    `${capitalRunLabel} · ${scenarioPrefix} · 총 매매 ${Number(result.total_trade_count || 0).toLocaleString()}회 · 압축훈련 ${Number(result.compressed_training_hours || 0).toLocaleString()}시간`,
  );
  const memory = result.memory || {};
  setText("capitalMemoryPath", memory.note_path ? `기록: ${memory.note_path}` : "장기기억 대기");

  const lessonsNode = el("#capitalLessons");
  const lessons = Array.isArray(result.lessons) ? result.lessons : [];
  if (lessonsNode) {
    lessonsNode.innerHTML = lessons.length
      ? lessons.map((lesson) => `<div class="capital-note">${escapeHtml(lesson)}</div>`).join("")
      : `<div class="capital-note">챌린지를 실행하면 구간별 교훈이 여기에 쌓입니다.</div>`;
  }

  const phaseNode = el("#capitalPhases");
  const phases = displayPhases;
  if (phaseNode) {
    phaseNode.innerHTML = phases.length
      ? phases.map((phase) => {
        const pending = phase.status === "PENDING" || phase.status === "PLANNED";
        const returnPct = Number(phase.return_pct || 0);
        const klass = pending ? "pending" : returnPct > 20 ? "strong" : returnPct > 0 ? "ok" : "weak";
        const symbolLabels = capitalPhaseSymbolLabelText(phase);
        const pointWarning = capitalPhasePointInTimeWarning(phase);
        return `
          <article class="capital-phase-card ${klass}">
            <div><strong>${escapeHtml(phase.label || `구간 ${phase.phase || ""}`)}</strong><span>${escapeHtml(phase.period || "-")}</span></div>
            <p>${escapeHtml(phase.purpose || "")}</p>
            <div class="capital-phase-metrics">
              <b>${pending ? "훈련 전" : `${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%`}</b>
              <small>수익률</small>
              <b>${pending ? "-" : `${money0(phase.final_equity || 0)}원`}</b>
              <small>최종금</small>
              <b>${pending ? "-" : `${Number(phase.max_drawdown_pct || 0).toFixed(2)}%`}</b>
              <small>MDD</small>
            </div>
            <small>${escapeHtml(phase.strategy || "-")} · 매매 ${Number(phase.trade_count || 0).toLocaleString()}회 · 승률 ${pending ? "-" : `${Number(phase.win_rate_pct || 0).toFixed(2)}%`}</small>
            <small>${escapeHtml(phase.training_run_label || `압축훈련 ${Number(phase.compressed_training_hours || 0).toLocaleString()}시간`)} · ${escapeHtml(phase.regime || "장세 구간")}</small>
            ${symbolLabels ? `<small class="capital-point-in-time-symbols">당시 종목명: ${escapeHtml(symbolLabels)}</small>` : ""}
            ${pointWarning ? `<small class="capital-point-in-time-warning">${escapeHtml(pointWarning)}</small>` : ""}
            <em>${escapeHtml(phase.lesson || "")}</em>
            <div class="capital-card-top-trades">
              <b>수익률 TOP3</b>
              ${renderCapitalTradeTopRows(phase.trade_journal_top10 || phase.top_trades || [], 3)}
            </div>
            <div class="capital-card-top-trades loss">
              <b>손실률 하위3</b>
              ${renderCapitalTradeTopRows(capitalPhaseBottomTrades(phase, 3), 3, "손실률 대기", "구간 훈련을 다시 돌리면 손실률 하위 매매가 표시됩니다.")}
            </div>
            <button class="capital-phase-train-button" data-capital-phase-train="${escapeHtml(String(phase.phase || ""))}">이 구간만 다시 훈련</button>
          </article>
        `;
      }).join("")
      : `<article class="capital-phase-card"><strong>훈련 구간 대기</strong><p>100억 프로젝트 실행을 누르면 구간별 결과가 표시됩니다.</p></article>`;
  }

  const taskNode = el("#capitalNextTasks");
  const tasks = Array.isArray(result.next_tasks) ? result.next_tasks : [];
  if (taskNode) {
    taskNode.innerHTML = tasks.length
      ? tasks.map((task, index) => `<div class="capital-task"><b>${index + 1}</b><span>${escapeHtml(task)}</span></div>`).join("")
      : `<div class="capital-task"><b>1</b><span>챌린지를 실행하면 AI가 다음 개선 과제를 기록합니다.</span></div>`;
  }
  updateCapitalSummaryCopyButton();
}

async function loadCapitalChallenge(force = false, options = {}) {
  const before = state.lastCapitalChallenge || {};
  const startedAt = performance.now();
  const userAction = Boolean(options.userAction || force);
  if (force) state.activeCapitalPhaseTraining = "";
  setCapitalButtonsBusy(true, force ? "run" : "refresh");
  setText("capitalState", force ? "100억 프로젝트 실행 중" : "최근 결과 조회 중");
  renderCapitalActionPanel(force ? "running" : "loading", {}, { before, force });
  if (userAction) {
    pushCapitalActionHistory(
      "start",
      force ? "100억 프로젝트 실행 요청" : "최근 결과 조회 요청",
      force ? "2000년부터 현재까지 전체 구간 훈련을 새로 시작합니다." : "저장된 최신 결과만 불러옵니다.",
    );
  }
  try {
    const endpoint = force
      ? "/api/agent/capital-challenge?force=1&async=1&start_year=2000&initial_cash=10000000&target_cash=10000000000"
      : "/api/agent/capital-challenge/status?run_if_due=0";
    const response = await fetch(endpoint);
    const payload = await response.json();
    if (Array.isArray(payload.scenarios)) {
      state.capitalScenarioCatalog = payload.scenarios;
    }
    if (force && (response.status === 202 || payload.running || payload.status === "RUNNING")) {
      if (!response.ok && response.status !== 202) throw new Error(payload.error || "100억 프로젝트 실행 시작 실패");
      setText("capitalState", `백그라운드 실행 중 · ${Number(payload.progress_pct || 0).toFixed(1)}% · ${formatDateTimeShort(payload.started_at)}`);
      renderCapitalActionPanel("running", state.lastCapitalChallenge || {}, { before, force, job: payload });
      if (userAction) {
        pushCapitalActionHistory(
          "running",
          payload.accepted === false ? "기존 실행 작업 확인" : "백그라운드 실행 시작",
          `진행률 ${Number(payload.progress_pct || 0).toFixed(1)}% · 상태를 자동으로 확인합니다.`,
        );
      }
      addLog(payload.accepted === false ? "100억 프로젝트가 이미 실행 중이라 기존 작업을 계속 확인합니다." : "100억 프로젝트 백그라운드 실행 시작");
      scheduleCapitalChallengeJobPoll(before, startedAt);
      return;
    }
    const result = payload.latest || payload;
    if (Array.isArray(payload.scenarios)) result.scenarios = payload.scenarios;
    if (payload.state) result.auto_state = payload.state;
    if (payload.auto) result.auto_status = payload.auto.status;
    if (!response.ok) throw new Error(result.error || "100억 프로젝트 조회 실패");
    renderCapitalChallenge(result);
    const elapsed = (performance.now() - startedAt) / 1000;
    renderCapitalActionPanel(force ? "completed" : "loaded", result, { before, force, elapsed_seconds: elapsed, auto: payload.auto || {} });
    if (userAction) {
      pushCapitalActionHistory(
        "success",
        force ? "100억 프로젝트 결과 갱신" : "최근 결과 조회 완료",
        force
          ? `진행률 ${Number(result.progress_pct || 0).toFixed(4)}% · 달성 ${Number(result.achieved_multiple || 0).toFixed(4)}배 · ${elapsed.toFixed(1)}초`
          : `기록 ${result.id || "ID 없음"} · 진행률 ${Number(result.progress_pct || 0).toFixed(4)}%`,
      );
    }
    addLog(force ? `100억 프로젝트 실행 완료: ${Number(result.achieved_multiple || 0).toFixed(4)}배 / 진행률 ${Number(result.progress_pct || 0).toFixed(4)}% / ${elapsed.toFixed(1)}초` : "100억 프로젝트 최근 결과만 조회");
  } catch (error) {
    setText("capitalState", "실패");
    renderCapitalActionPanel("error", {}, { before, force, error: error.message });
    if (userAction) pushCapitalActionHistory("error", force ? "100억 프로젝트 실행 실패" : "최근 결과 조회 실패", error.message);
    setCapitalButtonsBusy(false);
    addLog(`100억 프로젝트 실패: ${error.message}`);
  } finally {
    if (!force) setCapitalButtonsBusy(false);
  }
}

function runCapitalChallenge() {
  loadCapitalChallenge(true, { userAction: true });
}

async function runCapitalPhaseTraining(phaseId = "") {
  const selected = String(phaseId || "").trim();
  if (!selected) return;
  const before = state.lastCapitalChallenge || {};
  const startedAt = performance.now();
  state.activeCapitalPhaseTraining = selected;
  setCapitalButtonsBusy(true, "phase", selected);
  setText("capitalState", `구간별 훈련 시작 · ${capitalPhaseDisplayName(selected) || selected}`);
  renderCapitalActionPanel("running", state.lastCapitalChallenge || {}, {
    before,
    force: true,
    action: "phase",
    phase_id: selected,
    job: { mode: "phase", phase_id: selected, progress_pct: 0, current_label: "선택 구간 훈련 준비 중" },
  });
  pushCapitalActionHistory(
    "start",
    "구간별 훈련 요청",
    `${capitalPhaseDisplayName(selected) || selected} 구간만 따로 다시 돌립니다.`,
  );
  try {
    const response = await fetch(`/api/agent/capital-challenge/phase?async=1&start_year=2000&initial_cash=10000000&target_cash=10000000000&phase=${encodeURIComponent(selected)}`);
    const payload = await response.json();
    if (!response.ok && response.status !== 202) throw new Error(payload.error || "구간별 훈련 시작 실패");
    renderCapitalActionPanel("running", state.lastCapitalChallenge || {}, { before, force: true, job: payload });
    pushCapitalActionHistory(
      "running",
      "구간별 훈련 접수",
      `${capitalPhaseDisplayName(selected) || selected} · 진행률 ${Number(payload.progress_pct || 0).toFixed(1)}%`,
    );
    addLog(`구간별 훈련 시작: ${selected}`);
    scheduleCapitalChallengeJobPoll(before, startedAt);
  } catch (error) {
    setText("capitalState", "구간별 훈련 실패");
    renderCapitalActionPanel("error", {}, { before, force: true, error: error.message, action: "phase", phase_id: selected });
    pushCapitalActionHistory("error", "구간별 훈련 실패", `${capitalPhaseDisplayName(selected) || selected} · ${error.message}`);
    setCapitalButtonsBusy(false);
    state.activeCapitalPhaseTraining = "";
    addLog(`구간별 훈련 실패: ${error.message}`);
  }
}

function hundredLabRiskGrade(maxDrawdownPct = 0) {
  const mdd = Math.abs(Number(maxDrawdownPct || 0));
  if (mdd >= 50) return { className: "risk-high", label: "낙폭 위험" };
  if (mdd >= 30) return { className: "risk-mid", label: "낙폭 주의" };
  return { className: "risk-low", label: "낙폭 양호" };
}

function hundredLabRiskEfficiency(row = {}) {
  const multiple = Number(row.multiple || 0);
  const mdd = Math.max(Math.abs(Number(row.max_drawdown_pct || 0)), 1);
  return multiple / mdd;
}

function hundredLabCandidateReason(row = {}) {
  const multiple = Number(row.multiple || 0);
  const mdd = Math.abs(Number(row.max_drawdown_pct || 0));
  const winRate = Number(row.win_rate_pct || 0);
  const trades = Number(row.trade_count || 0);
  const efficiency = hundredLabRiskEfficiency(row);
  const parts = [];

  if (multiple >= 10) parts.push("배수 매우 우수");
  else if (multiple >= 3) parts.push("배수 우수");
  else if (multiple >= 1.5) parts.push("방향성 양호");
  else parts.push("성과 검증 필요");

  if (mdd < 20) parts.push("낙폭 방어 양호");
  else if (mdd < 35) parts.push("낙폭 관리권");
  else if (mdd < 50) parts.push("낙폭 주의");
  else parts.push("낙폭 위험");

  if (winRate >= 60) parts.push("승률 우수");
  else if (winRate >= 45) parts.push("승률 보통");
  else parts.push("승률 보강 필요");

  if (trades >= 100) parts.push("거래 표본 충분");
  else if (trades >= 30) parts.push("거래 표본 보통");
  else parts.push("표본 부족");

  if (efficiency >= 0.2) parts.push("위험효율 양호");
  return parts.slice(0, 5).join(" · ");
}

function renderHundredBillionLab(status = {}) {
  const result = status.result || {};
  const best = result.best || {};
  const running = Boolean(status.running);
  const verificationBlocked = !running && (result.status === "VERIFICATION_BLOCKED" || status.result_verification_status === "VERIFICATION_BLOCKED");
  const progress = Number(status.progress_pct || 0);
  const tested = Number(result.tested || 0);
  const planned = Number(result.planned || tested || 0);
  const completedProgress = planned > 0 ? Math.min((tested / planned) * 100, 100) : (result.ok ? 100 : 0);
  const visibleProgress = running ? Math.max(0, Math.min(progress, 100)) : completedProgress;
  setText(
    "hundredLabState",
    running
      ? `연구 중 · ${progress.toFixed(1)}% · ${status.mode || "-"}`
      : verificationBlocked ? "검증대기 · 전체 거래원장 필요" : result.ok ? `최근 최고 ${Number(best.multiple || 0).toFixed(4)}배` : (status.status || "대기"),
  );
  state.lastHundredLabStatus = status;
  document.querySelectorAll("[data-hundred-lab-run]").forEach((button) => {
    const active = running && (button.dataset.hundredLabRun || "") === (status.mode || "");
    if (!button.dataset.idleTitle) button.dataset.idleTitle = button.getAttribute("title") || buttonHelp(button);
    button.classList.toggle("is-running", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    button.disabled = running;
    button.title = running
      ? active
        ? "현재 이 탐색 모드가 실행 중입니다. 멈추려면 중지를 누르세요."
        : "탐색 중에는 중지 후 다른 모드를 시작할 수 있습니다."
      : button.dataset.idleTitle;
  });
  const stopButton = el("#stopHundredLab");
  if (stopButton) {
    stopButton.disabled = !running;
    stopButton.title = running ? "현재 전략 후보 탐색을 멈춥니다." : "탐색 실행 중에만 중지할 수 있습니다.";
  }
  const progressCard = el("#hundredLabProgressCard");
  if (progressCard) progressCard.style.setProperty("--hundred-lab-progress", `${visibleProgress}%`);
  setText(
    "hundredLabProgressText",
    running
      ? `탐색 중 · ${visibleProgress.toFixed(1)}%`
      : verificationBlocked ? `계산 완료 · 원장 검증대기` : result.ok ? `최근 탐색 완료 · ${visibleProgress.toFixed(1)}%` : "진행 대기",
  );
  setText(
    "hundredLabProgressMeta",
    running
      ? `${status.mode || "탐색"} 모드 · 검증 ${tested.toLocaleString()} / ${planned.toLocaleString()} 조합`
      : result.ok
        ? `검증 ${tested.toLocaleString()} / ${planned.toLocaleString()} 조합 · 최고 ${Number(best.multiple || 0).toFixed(4)}배`
        : "탐색을 시작하면 진행률과 검증 조합 수가 여기에 표시됩니다.",
  );
  setText(
    "hundredLabRunLockHint",
    running
      ? "탐색 중에는 다른 모드가 잠깁니다. 다른 모드를 원하면 중지 후 다시 선택하세요."
      : verificationBlocked ? "수익률은 표시만 하며 전체 거래원장 재생성·대사가 끝날 때까지 점수와 실전에 사용하지 않습니다." : result.ok ? "탐색 완료 상태입니다. 새 모드를 누르면 새 후보 탐색을 시작합니다." : "탐색 대기 중입니다. 원하는 모드를 눌러 시작하세요.",
  );
  setText("hundredLabUpdatedAt", `최근 확인: ${formatDateTimeShort(new Date().toISOString())}`);
  const summaryNode = el("#hundredLabSummary");
  if (summaryNode) {
    summaryNode.innerHTML = `
      <div><b>${Number(best.multiple || 0).toFixed(4)}배</b><small>최고 배수</small></div>
      <div><b>${money0(best.final_equity || 0)}원</b><small>최고 최종금</small></div>
      <div><b>${Number(best.max_drawdown_pct || 0).toFixed(2)}%</b><small>MDD</small></div>
      <div><b>${tested.toLocaleString()} / ${planned.toLocaleString()}</b><small>검증 조합</small></div>
    `;
  }
  const topNode = el("#hundredLabTop");
  const top = Array.isArray(result.top) ? result.top : [];
  const topTen = top.slice(0, 10);
  const riskCounts = topTen.reduce((acc, row) => {
    const risk = hundredLabRiskGrade(row.max_drawdown_pct).className;
    acc[risk] = (acc[risk] || 0) + 1;
    return acc;
  }, { "risk-low": 0, "risk-mid": 0, "risk-high": 0 });
  const visibleTop = state.hideHundredLabHighRisk
    ? topTen.filter((row) => hundredLabRiskGrade(row.max_drawdown_pct).className !== "risk-high")
    : topTen;
  if (state.sortHundredLabByEfficiency) {
    visibleTop.sort((a, b) => hundredLabRiskEfficiency(b) - hundredLabRiskEfficiency(a));
  }
  const hideRiskButton = el("#toggleHundredLabHideRisk");
  if (hideRiskButton) {
    hideRiskButton.textContent = state.hideHundredLabHighRisk ? "낙폭 위험 숨김 ON" : "낙폭 위험 숨김 OFF";
    hideRiskButton.setAttribute("aria-pressed", state.hideHundredLabHighRisk ? "true" : "false");
    hideRiskButton.disabled = !topTen.length || !riskCounts["risk-high"];
    hideRiskButton.title = riskCounts["risk-high"]
      ? "낙폭 위험 후보를 화면에서 숨기거나 다시 표시합니다."
      : "현재 TOP10에는 낙폭 위험 후보가 없습니다.";
  }
  const efficiencySortButton = el("#toggleHundredLabEfficiencySort");
  if (efficiencySortButton) {
    efficiencySortButton.textContent = state.sortHundredLabByEfficiency ? "위험효율순 ON" : "위험효율순 OFF";
    efficiencySortButton.setAttribute("aria-pressed", state.sortHundredLabByEfficiency ? "true" : "false");
    efficiencySortButton.disabled = !topTen.length;
    efficiencySortButton.title = topTen.length
      ? "현재 표시 후보를 위험효율이 높은 순서로 재정렬합니다."
      : "탐색 결과가 생기면 위험효율순으로 볼 수 있습니다.";
  }
  setText(
    "hundredLabTopCount",
    top.length
      ? `표시 ${visibleTop.length.toLocaleString()}개${state.hideHundredLabHighRisk ? "(위험 숨김)" : ""} · ${state.sortHundredLabByEfficiency ? "위험효율순" : "최고 배수순"} · 양호 ${riskCounts["risk-low"]} / 주의 ${riskCounts["risk-mid"]} / 위험 ${riskCounts["risk-high"]}`
      : "결과 대기",
  );
  const copyButton = el("#copyHundredLabTop");
  if (copyButton) {
    copyButton.disabled = !visibleTop.length;
    copyButton.textContent = visibleTop.length
      ? state.hideHundredLabHighRisk ? `화면 ${visibleTop.length}개 복사` : `TOP${visibleTop.length} 복사`
      : "후보 없음";
    copyButton.title = visibleTop.length
      ? "현재 화면에 표시된 상위 전략 후보 요약을 클립보드에 복사합니다."
      : state.hideHundredLabHighRisk && top.length ? "필터 때문에 표시된 후보가 없습니다. 전체 후보를 다시 보거나 필터를 끄면 복사할 수 있습니다." : "탐색 결과가 생기면 상위 후보를 복사할 수 있습니다.";
  }
  const downloadButton = el("#downloadHundredLabTop");
  if (downloadButton) {
    downloadButton.disabled = !visibleTop.length;
    downloadButton.textContent = visibleTop.length
      ? state.hideHundredLabHighRisk ? `화면 ${visibleTop.length}개 저장` : `TOP${visibleTop.length} 저장`
      : "저장 대기";
    downloadButton.title = visibleTop.length
      ? "현재 화면에 표시된 상위 전략 후보 요약을 Markdown 파일로 저장합니다."
      : state.hideHundredLabHighRisk && top.length ? "필터 때문에 표시된 후보가 없습니다. 전체 후보를 다시 보거나 필터를 끄면 저장할 수 있습니다." : "탐색 결과가 생기면 상위 후보를 저장할 수 있습니다.";
  }
  if (topNode) {
    topNode.innerHTML = top.length
      ? visibleTop.length
        ? visibleTop.map((row, index) => {
        const risk = hundredLabRiskGrade(row.max_drawdown_pct);
        const efficiency = hundredLabRiskEfficiency(row);
        const reason = hundredLabCandidateReason(row);
        return `
          <div class="hundred-lab-top-card has-${risk.className} ${index < 3 ? `is-top-${index + 1}` : ""}">
            <strong><em>${index + 1}위</em>${escapeHtml(row.name || "-")}</strong>
            <span>${Number(row.multiple || 0).toFixed(4)}배 · ${money0(row.final_equity || 0)}원</span>
            <small>MDD ${Number(row.max_drawdown_pct || 0).toFixed(2)}% · 승률 ${Number(row.win_rate_pct || 0).toFixed(2)}% · 거래 ${Number(row.trade_count || 0).toLocaleString()}회</small>
            <p class="hundred-lab-reason">왜 후보인가: ${escapeHtml(reason)}</p>
            <i class="hundred-lab-risk ${risk.className}">${escapeHtml(risk.label)}</i>
            <i class="hundred-lab-efficiency">위험효율 ${efficiency.toFixed(3)}</i>
          </div>
        `;
      }).join("")
        : `<div class="hundred-lab-filter-empty"><strong>표시 후보 없음</strong><small>낙폭 위험 후보 숨김이 켜져 있어 현재 TOP10 후보가 모두 숨겨졌습니다.</small><button type="button" data-hundred-lab-show-all>전체 후보 다시 보기</button></div>`
      : `<div><strong>전략 후보 대기</strong><small>빠른 탐색이나 집중 탐색을 시작하면 후보 결과가 여기에 표시됩니다.</small></div>`;
  }
  if (state.hundredLabPollTimer) {
    clearTimeout(state.hundredLabPollTimer);
    state.hundredLabPollTimer = null;
  }
  if (running) {
    state.hundredLabPollTimer = setTimeout(() => loadHundredBillionLabStatus(false), 15000);
  }
}

function hundredLabTopSummaryText(status = state.lastHundredLabStatus || {}) {
  const result = status.result || {};
  const best = result.best || {};
  const topTen = Array.isArray(result.top) ? result.top.slice(0, 10) : [];
  const top = state.hideHundredLabHighRisk
    ? topTen.filter((row) => hundredLabRiskGrade(row.max_drawdown_pct).className !== "risk-high")
    : topTen;
  if (state.sortHundredLabByEfficiency) {
    top.sort((a, b) => hundredLabRiskEfficiency(b) - hundredLabRiskEfficiency(a));
  }
  const exportRiskCounts = top.reduce((acc, row) => {
    const risk = hundredLabRiskGrade(row.max_drawdown_pct).className;
    acc[risk] = (acc[risk] || 0) + 1;
    return acc;
  }, { "risk-low": 0, "risk-mid": 0, "risk-high": 0 });
  const tested = Number(result.tested || 0);
  const planned = Number(result.planned || tested || 0);
  return [
    "# 코덱스스톡 전략 후보 탐색기 상위 후보",
    "",
    `생성일: ${new Date().toLocaleString("ko-KR", { hour12: false })}`,
    `상태: ${status.running ? `탐색 중(${status.mode || "-"})` : verificationBlocked ? "검증대기" : result.ok ? "탐색 완료" : (status.status || "대기")}`,
    `화면 필터: ${state.hideHundredLabHighRisk ? "낙폭 위험 숨김 ON" : "낙폭 위험 숨김 OFF"}`,
    `정렬 기준: ${state.sortHundredLabByEfficiency ? "위험효율순" : "최고 배수순"}`,
    "위험효율: 배수 ÷ max(MDD%, 1). 높을수록 같은 낙폭 대비 더 큰 성과를 낸 후보",
    `기록 후보: ${top.length.toLocaleString()}개${state.hideHundredLabHighRisk ? " / 원본 TOP10에서 낙폭 위험 제외" : " / 원본 TOP10"}`,
    `낙폭 요약: 양호 ${exportRiskCounts["risk-low"]}개 / 주의 ${exportRiskCounts["risk-mid"]}개 / 위험 ${exportRiskCounts["risk-high"]}개`,
    `검증 조합: ${tested.toLocaleString()} / ${planned.toLocaleString()}`,
    `최고 기록: ${Number(best.multiple || 0).toFixed(4)}배 · ${money0(best.final_equity || 0)}원 · MDD ${Number(best.max_drawdown_pct || 0).toFixed(2)}%`,
    "",
    "## 상위 후보",
    ...(top.length
      ? top.map((row, index) => {
        const risk = hundredLabRiskGrade(row.max_drawdown_pct);
        const efficiency = hundredLabRiskEfficiency(row);
        const reason = hundredLabCandidateReason(row);
        return `${index + 1}. ${row.name || "-"} · ${Number(row.multiple || 0).toFixed(4)}배 · ${money0(row.final_equity || 0)}원 · MDD ${Number(row.max_drawdown_pct || 0).toFixed(2)}%(${risk.label}) · 위험효율 ${efficiency.toFixed(3)} · 승률 ${Number(row.win_rate_pct || 0).toFixed(2)}% · 거래 ${Number(row.trade_count || 0).toLocaleString()}회 · 근거 ${reason}`;
      })
      : [state.hideHundredLabHighRisk ? "현재 필터 기준으로 표시할 후보가 없습니다. 낙폭 위험 숨김을 끄면 전체 TOP10을 볼 수 있습니다." : "아직 복사할 후보가 없습니다. 빠른 탐색이나 집중 탐색을 먼저 실행하세요."]),
    "",
    "주의: 이 내용은 연구/모의훈련 기록이며 실전 수익을 보장하지 않습니다.",
  ].join("\n");
}

function toggleHundredLabHideRisk() {
  state.hideHundredLabHighRisk = !state.hideHundredLabHighRisk;
  try {
    localStorage.setItem(HUNDRED_LAB_HIDE_RISK_STORAGE_KEY, state.hideHundredLabHighRisk ? "1" : "0");
  } catch (_) {}
  renderHundredBillionLab(state.lastHundredLabStatus || {});
  addLog(state.hideHundredLabHighRisk ? "전략 후보 탐색기 낙폭 위험 후보 숨김" : "전략 후보 탐색기 낙폭 위험 후보 다시 표시");
}

function toggleHundredLabEfficiencySort() {
  state.sortHundredLabByEfficiency = !state.sortHundredLabByEfficiency;
  try {
    localStorage.setItem(HUNDRED_LAB_EFFICIENCY_SORT_STORAGE_KEY, state.sortHundredLabByEfficiency ? "1" : "0");
  } catch (_) {}
  renderHundredBillionLab(state.lastHundredLabStatus || {});
  addLog(state.sortHundredLabByEfficiency ? "전략 후보 탐색기 위험효율순 정렬" : "전략 후보 탐색기 최고 배수순 정렬");
}

async function copyHundredLabTop() {
  try {
    const top = state.lastHundredLabStatus?.result?.top || [];
    if (!Array.isArray(top) || !top.length) throw new Error("복사할 상위 후보가 아직 없습니다.");
    await copyTextToClipboard(hundredLabTopSummaryText());
    addLog("전략 후보 탐색기 상위 후보 요약 복사 완료");
    setText("hundredLabRunLockHint", `${state.hideHundredLabHighRisk ? "화면 후보" : "TOP10"} 요약을 클립보드에 복사했습니다.`);
  } catch (error) {
    addLog(`전략 후보 탐색기 상위 후보 복사 실패: ${error.message}`);
    setText("hundredLabRunLockHint", `상위 후보 복사 실패: ${error.message}`);
  }
}

async function downloadHundredLabTop() {
  try {
    const top = state.lastHundredLabStatus?.result?.top || [];
    if (!Array.isArray(top) || !top.length) throw new Error("저장할 상위 후보가 아직 없습니다.");
    const blob = new Blob([hundredLabTopSummaryText()], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `codexstock-hundred-lab-top${state.hideHundredLabHighRisk ? "-filtered" : ""}-${todayIso()}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    addLog("전략 후보 탐색기 상위 후보 Markdown 저장 시작");
    setText("hundredLabRunLockHint", `${state.hideHundredLabHighRisk ? "화면 후보" : "TOP10"} 요약을 Markdown 파일로 저장했습니다.`);
  } catch (error) {
    addLog(`전략 후보 탐색기 상위 후보 저장 실패: ${error.message}`);
    setText("hundredLabRunLockHint", `상위 후보 저장 실패: ${error.message}`);
  }
}

async function loadHundredBillionLabStatus(log = true) {
  const refreshButton = el("#refreshHundredLab");
  const previousLabel = refreshButton?.textContent || "상태 새로고침";
  if (log && refreshButton) {
    refreshButton.disabled = true;
    refreshButton.textContent = "확인중";
  }
  try {
    const response = await fetch("/api/agent/hundred-billion-lab/status");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "전략 실험실 상태 조회 실패");
    renderHundredBillionLab(result);
    if (log) addLog(result.running ? `전략 후보 탐색기 연구 중: ${Number(result.progress_pct || 0).toFixed(1)}%` : "전략 후보 탐색기 상태 조회");
  } catch (error) {
    setText("hundredLabState", "조회 실패");
    document.querySelectorAll("[data-hundred-lab-run]").forEach((button) => {
      button.classList.remove("is-running");
      button.disabled = false;
      if (button.dataset.idleTitle) button.title = button.dataset.idleTitle;
    });
    const stopButton = el("#stopHundredLab");
    if (stopButton) stopButton.disabled = true;
    addLog(`전략 후보 탐색기 조회 실패: ${error.message}`);
  } finally {
    if (log && refreshButton) {
      refreshButton.disabled = false;
      refreshButton.textContent = previousLabel;
    }
  }
}

async function runHundredBillionLab(mode = "focus") {
  setText("hundredLabState", `${mode} 시작 중`);
  const previousResult = state.lastHundredLabStatus?.result || {};
  renderHundredBillionLab({ running: true, progress_pct: 0, mode, status: "starting", result: previousResult });
  try {
    const response = await fetch("/api/agent/hundred-billion-lab/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "전략 실험실 시작 실패");
    renderHundredBillionLab(result);
    addLog(`전략 후보 탐색기 시작: ${mode}`);
  } catch (error) {
    setText("hundredLabState", "시작 실패");
    document.querySelectorAll("[data-hundred-lab-run]").forEach((button) => {
      button.classList.remove("is-running");
      button.disabled = false;
      if (button.dataset.idleTitle) button.title = button.dataset.idleTitle;
    });
    const stopButton = el("#stopHundredLab");
    if (stopButton) stopButton.disabled = true;
    addLog(`전략 후보 탐색기 시작 실패: ${error.message}`);
  }
}

async function stopHundredBillionLab() {
  setText("hundredLabState", "중지 중");
  const stopButton = el("#stopHundredLab");
  if (stopButton) stopButton.disabled = true;
  try {
    const response = await fetch("/api/agent/hundred-billion-lab/stop", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "전략 실험실 중지 실패");
    renderHundredBillionLab(result);
    addLog("전략 후보 탐색기 중지");
  } catch (error) {
    setText("hundredLabState", "중지 실패");
    document.querySelectorAll("[data-hundred-lab-run]").forEach((button) => {
      button.classList.remove("is-running");
      button.disabled = false;
      if (button.dataset.idleTitle) button.title = button.dataset.idleTitle;
    });
    if (stopButton) stopButton.disabled = true;
    addLog(`전략 후보 탐색기 중지 실패: ${error.message}`);
  }
}

function aiTournamentRunFromPayload(payload = {}) {
  if (Array.isArray(payload.rankings)) return payload;
  const runs = Array.isArray(payload.runs) ? payload.runs : [];
  return runs[0] || {};
}

function aiTournamentPct(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${number >= 0 ? "+" : ""}${number.toFixed(digits)}%`;
}

function aiTournamentNeedsPriceReview(row = {}) {
  return Boolean(
    row.unverified_price_outlier
    || row.needs_price_reconciliation
    || row.price_reconciliation_status === "needs_review"
    || row.quarantined
  );
}

function aiTournamentPriceReviewBadge(row = {}) {
  return "";
}

function aiTournamentAverageNote(row = {}) {
  const status = String(row.return_claim_status || "").toLowerCase();
  if (status === "trusted") return "공식 검증 통과";
  if (status === "mixed") return "일부 검증 · 일부 검토";
  if (status) return "수익률 대사 필요";
  return "";
}

function aiTournamentTrustedReturnBadge(row = {}) {
  const status = String(row.return_claim_status || "").toLowerCase();
  const className = status === "trusted" ? "up" : status === "mixed" ? "warn" : "down";
  const label = aiTournamentAverageNote(row) || "검증 대기";
  return `<span class="${className}">${escapeHtml(label)}</span>`;
}

function aiTournamentOfficialReturnLabel(row = {}) {
  if (row.trusted_avg_return_pct !== null && row.trusted_avg_return_pct !== undefined) {
    return `공식검증 평균 ${aiTournamentPct(row.trusted_avg_return_pct)}`;
  }
  if (row.quarantined_avg_return_pct !== null && row.quarantined_avg_return_pct !== undefined) {
    return `검토필요 평균 ${aiTournamentPct(row.quarantined_avg_return_pct)}`;
  }
  return `평균수익 ${aiTournamentPct(row.avg_return_pct)}`;
}

function aiTournamentOfficialBestLabel(row = {}) {
  if (row.trusted_best_return_pct !== null && row.trusted_best_return_pct !== undefined) {
    return `공식검증 최고 ${aiTournamentPct(row.trusted_best_return_pct)}`;
  }
  if (row.quarantined_best_return_pct !== null && row.quarantined_best_return_pct !== undefined) {
    return `검토필요 최고 ${aiTournamentPct(row.quarantined_best_return_pct)}`;
  }
  return `최고 ${aiTournamentPct(row.best_return_pct)}`;
}

function aiTournamentSymbolNames(symbols = [], atDate = "") {
  return (Array.isArray(symbols) ? symbols : [])
    .map((symbol) => pointInTimeDisplayName(symbol, atDate, { symbol }))
    .filter(Boolean)
    .join(", ") || "기본 종목군";
}

function aiTournamentStaffName(row = {}) {
  if (row.display_name) return row.display_name;
  if (row.persona_name && row.name) return `${row.persona_name} · ${row.name}`;
  return row.name || row.contestant_id || "AI 직원";
}

function aiTournamentStaffProfile(row = {}) {
  const pieces = [row.call_sign ? `${row.call_sign} 팀원` : "", row.role || "", row.profile || ""].filter(Boolean);
  return pieces.join(" · ") || "-";
}

function renderAiTournamentScenarios(scenarios = []) {
  const select = el("#aiTournamentPhase");
  if (!select || !Array.isArray(scenarios) || !scenarios.length) return;
  const current = select.value || "LEADER-2024";
  select.innerHTML = scenarios.map((scenario) => `
    <option value="${escapeHtml(scenario.phase || "")}" data-start="${escapeHtml(scenario.start || "")}" data-end="${escapeHtml(scenario.end || "")}" data-symbols="${escapeHtml((scenario.symbols || []).join(","))}">
      ${escapeHtml(scenario.label || scenario.phase || "-")}
    </option>
  `).join("");
  select.value = scenarios.some((scenario) => String(scenario.phase) === current) ? current : String(scenarios[0].phase || "");
}

function applyAiTournamentPhaseToForm() {
  const selected = el("#aiTournamentPhase")?.selectedOptions?.[0];
  if (!selected) return;
  if (selected.dataset.start && el("#aiTournamentStart")) el("#aiTournamentStart").value = selected.dataset.start;
  if (selected.dataset.end && el("#aiTournamentEnd")) el("#aiTournamentEnd").value = selected.dataset.end;
  if (selected.dataset.symbols && el("#aiTournamentSymbols")) el("#aiTournamentSymbols").value = selected.dataset.symbols;
}

function renderAiTournamentChampions(entries = []) {
  state.aiTournamentChampions = Array.isArray(entries) ? entries : [];
  const select = el("#aiTournamentChampionPreset");
  if (!select) return;
  select.innerHTML = [
    `<option value="">한투 챔피언 직접 선택 안 함</option>`,
    ...state.aiTournamentChampions.map((entry) => `
      <option value="${escapeHtml(entry.id || "")}">
        ${escapeHtml(entry.contest_name || "실전투자대회")} · ${escapeHtml(entry.league || "")} · ${escapeHtml(entry.champion_name || "챔피언")} ${aiTournamentPct(entry.return_pct)}
      </option>
    `),
  ].join("");
  setText("aiTournamentChampionSource", state.aiTournamentChampions.length ? `한투/공개 챔피언 ${state.aiTournamentChampions.length}명` : "챔피언 데이터 없음");
}

function selectedAiTournamentChampion() {
  const id = el("#aiTournamentChampionPreset")?.value || "";
  return state.aiTournamentChampions.find((entry) => String(entry.id || "") === id) || null;
}

function matchingAiTournamentChampionReturns(selected = selectedAiTournamentChampion()) {
  if (!selected) return [];
  const contestId = String(selected.contest_id || "");
  const market = String(selected.market || "");
  return state.aiTournamentChampions
    .filter((entry) => (!contestId || String(entry.contest_id || "") === contestId) && (!market || String(entry.market || "") === market))
    .map((entry) => Number(entry.return_pct || 0))
    .filter((value) => Number.isFinite(value));
}

function applyAiTournamentChampionCondition() {
  const selected = selectedAiTournamentChampion();
  if (!selected) {
    addLog("한투 챔피언 조건: 선택된 챔피언이 없습니다.");
    return;
  }
  if (selected.start_date && el("#aiTournamentStart")) el("#aiTournamentStart").value = selected.start_date;
  if (selected.end_date && el("#aiTournamentEnd")) el("#aiTournamentEnd").value = selected.end_date;
  if (selected.initial_cash && el("#aiTournamentCash")) el("#aiTournamentCash").value = Math.round(Number(selected.initial_cash));
  const returns = matchingAiTournamentChampionReturns(selected);
  if (returns.length && el("#aiTournamentContestReturns")) el("#aiTournamentContestReturns").value = returns.join(",");
  if (el("#aiTournamentUseChampions")) el("#aiTournamentUseChampions").checked = true;
  setText("aiTournamentChampionSource", `${selected.champion_name || "챔피언"} 조건 적용 · ${selected.period_label || `${selected.start_date || "-"}~${selected.end_date || "-"}`}`);
  addLog(`한투 챔피언 조건 적용: ${selected.contest_name || "-"} · ${selected.league || "-"} · ${selected.return_pct}%`);
}

async function loadAiTournamentChampions(log = false) {
  try {
    const response = await fetch("/api/ai-tournament/champions");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "한투 챔피언 데이터 조회 실패");
    renderAiTournamentChampions(result.entries || []);
    if (log) addLog("한투 실전투자대회 챔피언 데이터 조회");
  } catch (error) {
    setText("aiTournamentChampionSource", "챔피언 조회 실패");
    addLog(`한투 챔피언 데이터 조회 실패: ${error.message}`);
  }
}

function aiTournamentContestRankFor(row = {}, contestRank = {}) {
  const ranks = Array.isArray(contestRank.staff_ranks) ? contestRank.staff_ranks : [];
  return ranks.find((item) => item.contestant_id === row.contestant_id) || null;
}

function aiTournamentTradeList(trades = [], label = "주요 매매") {
  const rows = Array.isArray(trades) ? trades.slice(0, 3) : [];
  if (!rows.length) return "";
  return `
    <div class="ai-tournament-trades">
      <b>${escapeHtml(label)}</b>
      ${rows.map((trade) => `
        <span>${escapeHtml(trade.display_name || pointInTimeDisplayName(trade.symbol, trade.entry_date || trade.date || trade.name_as_of_date, trade))} · ${escapeHtml(trade.side || "-")} · ${aiTournamentPct(trade.pnl_pct)}</span>
      `).join("")}
    </div>
  `;
}

function aiTournamentTradeList(trades = [], label = "주요 매매") {
  const rows = Array.isArray(trades) ? trades.slice(0, 3) : [];
  if (!rows.length) return "";
  return `
    <div class="ai-tournament-trades">
      <b>${escapeHtml(label)}</b>
      ${rows.map((trade) => `
        <span class="${aiTournamentNeedsPriceReview(trade) ? "needs-price-review" : ""}">
          ${escapeHtml(trade.display_name || pointInTimeDisplayName(trade.symbol, trade.entry_date || trade.date || trade.name_as_of_date, trade))}
          · ${escapeHtml(trade.side || "-")}
          · ${aiTournamentPct(trade.pnl_pct)}
          ${aiTournamentPriceReviewBadge(trade)}
        </span>
      `).join("")}
    </div>
  `;
}

function aiTournamentLongHorizonClaim(row = {}) {
  const evidence = row.performance_evidence || {};
  const official = evidence.passed === true && row.performance_claim_status === "official";
  const cagrValue = official && row.official_cagr_pct !== null && row.official_cagr_pct !== undefined
    ? row.official_cagr_pct
    : row.cagr_pct;
  const totalValue = official && row.official_total_return_pct !== null && row.official_total_return_pct !== undefined
    ? row.official_total_return_pct
    : row.total_return_pct;
  const prefix = official ? "공식" : "참고용";
  return {
    official,
    cagrValue,
    totalValue,
    cagrLabel: cagrValue === null || cagrValue === undefined ? "-" : `${prefix} ${aiTournamentPct(cagrValue)}`,
    totalLabel: totalValue === null || totalValue === undefined ? "-" : `${prefix} ${aiTournamentPct(totalValue)}`,
    statusLabel: official ? "공식 검증 통과" : "참고용 · 공식 미검증",
    confidence: Number(evidence.confidence_score || 0),
    blockerCount: Array.isArray(evidence.blockers) ? evidence.blockers.length : 0,
    actualPeriod: evidence.actual_start_date && evidence.actual_end_date
      ? `${evidence.actual_start_date}~${evidence.actual_end_date}`
      : "실제 데이터 기간 미확인",
  };
}

function renderAiTournament(payload = {}) {
  const run = aiTournamentRunFromPayload(payload);
  const rawRankings = Array.isArray(run.rankings) ? run.rankings : [];
  const rankings = rawRankings.filter((row) => !aiTournamentNeedsPriceReview(row));
  const errors = Array.isArray(run.errors) ? run.errors : [];
  const contestRank = run.contest_rank || {};
  const champion = run.champion || rankings[0] || {};
  const championContestRank = aiTournamentContestRankFor(champion, contestRank) || {};
  const championGate = champion.competition_gate || {};
  const championShadow = champion.shadow_validation || run.shadow_validation || {};
  const championStress = champion.monte_carlo_stress || championGate.monte_carlo_stress || {};
  const championWalkForward = champion.walk_forward || run.walk_forward || {};
  const championBiasAudit = champion.bias_audit || run.bias_audit || {};
  const championPriceAudit = champion.price_currency_unit_audit || {};
  const isCostedLongHorizon = Boolean(run.costed_result_overlay_applied);
  const championLongHorizon = aiTournamentLongHorizonClaim(champion);
  const hasResult = Boolean(rankings.length);
  state.lastAiTournament = run;
  const runButton = el("#runAiTournamentMini");
  if (runButton) {
    runButton.disabled = state.aiTournamentRunning;
    runButton.textContent = state.aiTournamentRunning ? "미니리그 실행 중" : "미니리그 실행";
    runButton.title = state.aiTournamentRunning
      ? "AI 직원들이 같은 조건으로 과거장 리그를 치르는 중입니다."
      : "현재 입력값으로 AI 직원 미니리그를 실행합니다.";
  }
  setText(
    "aiTournamentState",
    state.aiTournamentRunning
      ? "실행 중"
      : hasResult
        ? `챔피언 ${aiTournamentStaffName(champion)} · ${isCostedLongHorizon ? `${championLongHorizon.statusLabel} CAGR ${aiTournamentPct(championLongHorizon.cagrValue)}` : aiTournamentPct(champion.total_return_pct)}`
        : errors.length
          ? `완주 실패 · 오류 ${errors.length}개`
        : "결과 대기",
  );

  const championNode = el("#aiTournamentChampion");
  if (championNode) {
    championNode.innerHTML = hasResult ? `
      <article>
        <small>${isCostedLongHorizon ? `${championLongHorizon.statusLabel} · 장기 결과 1위` : "최근 리그 챔피언"}</small>
        <strong>${escapeHtml(aiTournamentStaffName(champion))} <em>${escapeHtml(champion.role || "")}</em></strong>
        <small>${escapeHtml(aiTournamentStaffProfile(champion))}</small>
        <p>${escapeHtml(champion.strategy_name || "-")} 전략으로 ${escapeHtml(isCostedLongHorizon ? championLongHorizon.actualPeriod : `${run.start_date || "-"}~${run.end_date || "-"}`)} 구간을 달렸습니다.${isCostedLongHorizon ? " 수수료·세금·슬리피지 원장까지 확인해야 공식 성과가 됩니다." : ""}</p>
        <div>
          <span class="${Number((isCostedLongHorizon ? championLongHorizon.cagrValue : champion.total_return_pct) || 0) >= 0 ? "up" : "down"}">${isCostedLongHorizon ? `연평균 CAGR ${championLongHorizon.cagrLabel}` : aiTournamentPct(champion.total_return_pct)}</span>
          ${isCostedLongHorizon ? `<span>총수익 ${championLongHorizon.totalLabel}</span>` : ""}
          ${isCostedLongHorizon ? `<span class="${championLongHorizon.official ? "up" : "down"}">${championLongHorizon.statusLabel} · 증거 ${championLongHorizon.confidence.toFixed(1)}점 · 차단 ${championLongHorizon.blockerCount}건</span>` : ""}
          <span>MDD ${aiTournamentPct(champion.max_drawdown_pct, 2)}</span>
          <span>승률 ${aiTournamentPct(champion.win_rate_pct, 1)}</span>
          ${!isCostedLongHorizon ? `<span>점수 ${Number(champion.score || 0).toFixed(2)}</span>` : ""}
          <span class="ai-tournament-grade">등급 ${escapeHtml(championGate.grade || "-")} · 신뢰도 ${Number(championGate.confidence_score || 0).toFixed(1)}</span>
          <span>${escapeHtml(championGate.status || "게이트 대기")}</span>
          ${championStress.status ? `<span class="${championStress.passed ? "up" : "down"}">스트레스 ${escapeHtml(championStress.status)} · 플러스 ${Number(championStress.positive_rate_pct || 0).toFixed(1)}%</span>` : ""}
          ${championShadow.status ? `<span class="${championShadow.passed ? "up" : "down"}">${escapeHtml(championShadow.status)} · 평균 ${aiTournamentPct(championShadow.avg_return_pct)}</span>` : ""}
          ${championWalkForward.status ? `<span class="${championWalkForward.passed ? "up" : "down"}">${escapeHtml(championWalkForward.status)} · 미래 30% ${aiTournamentPct(championWalkForward.out_of_sample_result?.return_pct)}</span>` : ""}
          ${championBiasAudit.status ? `<span class="${championBiasAudit.passed ? "up" : "down"}">${escapeHtml(championBiasAudit.status)}</span>` : ""}
          ${championPriceAudit.schema ? `<span class="${championPriceAudit.passed ? "up" : "down"}">${championPriceAudit.passed ? "가격·통화·단위 검증 통과" : `가격·통화·단위 검토 ${Number(championPriceAudit.blockers?.length || 0)}건`}</span>` : ""}
          ${championContestRank.estimated_rank ? `<span>${escapeHtml(contestRank.label || "실전대회")} 예상 ${Number(championContestRank.estimated_rank)}등/${Number(championContestRank.field_size)}명</span>` : ""}
        </div>
      </article>
      <article>
        <small>${isCostedLongHorizon ? (championLongHorizon.official ? "공식 표시 기준" : "참고용 표시 기준") : "같은 조건"}</small>
        <strong>${formatKrw(run.initial_cash || 0)}</strong>
        <p>${isCostedLongHorizon ? escapeHtml(championLongHorizon.official ? (run.display_note || "공식 장기성과") : "미검증 결과는 직원 점수와 실전 후보에 반영하지 않습니다.") : escapeHtml(aiTournamentSymbolNames(run.symbols, run.start_date))}</p>
        <div>
          <span>${Number(run.finished_count || rankings.length || 0)}명 완주</span>
          <span>${Number(run.error_count || 0)}개 오류</span>
        <span>${escapeHtml(run.safety || "Paper 전용")}</span>
        </div>
      </article>
    ` : errors.length ? `
      <article>
        <small>최근 리그 완주 실패</small>
        <strong>구간 또는 데이터 조건 확인 필요</strong>
        <p>${escapeHtml(errors[0]?.error || "리그 완주 결과가 없습니다.")}</p>
      </article>
      <article>
        <small>입력 조건</small>
        <strong>${escapeHtml(run.start_date || "-")} ~ ${escapeHtml(run.end_date || "-")}</strong>
        <p>${escapeHtml(aiTournamentSymbolNames(run.symbols, run.start_date))}</p>
        <div>
          <span>${Number(run.finished_count || 0)}명 완주</span>
          <span>${Number(run.error_count || errors.length || 0)}개 오류</span>
          <span>최소 40거래일 이상 권장</span>
        </div>
      </article>
    ` : `
      <article>
        <small>AI 직원 왕중왕전 대기</small>
        <strong>미니리그를 실행해보세요</strong>
        <p>직원들이 같은 시장에서 겨루고, 챔피언과 실패 패턴을 장기기억에 남깁니다.</p>
      </article>
    `;
  }

  const rankingsNode = el("#aiTournamentRankings");
  if (rankingsNode) {
    rankingsNode.innerHTML = rankings.length ? rankings.map((row) => {
      const isChampion = Number(row.rank || 0) === 1;
      const gap = row.benchmark_gap_pct === null || row.benchmark_gap_pct === undefined ? "-" : `${aiTournamentPct(row.benchmark_gap_pct)}p`;
      const contestRow = aiTournamentContestRankFor(row, contestRank);
      const gate = row.competition_gate || {};
      const stress = row.monte_carlo_stress || gate.monte_carlo_stress || {};
      const failedCount = Array.isArray(gate.failed_checks) ? gate.failed_checks.length : 0;
      const priceReview = aiTournamentNeedsPriceReview(row);
      const benchmarkCagrGap = row.benchmark_cagr_gap_pctp === null || row.benchmark_cagr_gap_pctp === undefined
        ? "-"
        : `${aiTournamentPct(row.benchmark_cagr_gap_pctp)}p`;
      const longHorizon = aiTournamentLongHorizonClaim(row);
      return `
        <article class="${isChampion ? "is-champion" : ""} ${priceReview ? "needs-price-review" : ""}">
          <div class="ai-tournament-rank-head">
            <strong>${Number(row.rank || 0)}위 · ${escapeHtml(aiTournamentStaffName(row))}</strong>
            <span class="${Number((isCostedLongHorizon ? longHorizon.cagrValue : row.total_return_pct) || 0) >= 0 ? "up" : "down"}">${isCostedLongHorizon ? `CAGR ${longHorizon.cagrLabel}` : aiTournamentPct(row.total_return_pct)}</span>
          </div>
          <p>${escapeHtml(aiTournamentStaffProfile(row))} · ${escapeHtml(row.strategy_name || row.strategy_mode || "-")}</p>
          <small>선택 종목: ${escapeHtml(aiTournamentSymbolNames(row.selected_symbols || [], run.start_date))}</small>
          <small>선택 기준: ${escapeHtml(row.selection_reason || "-")}</small>
          ${isCostedLongHorizon ? `<small>${longHorizon.statusLabel}: 총수익 ${longHorizon.totalLabel} · CAGR ${longHorizon.cagrLabel} · SPY 대비 CAGR ${benchmarkCagrGap} · 증거 ${longHorizon.confidence.toFixed(1)}점 · 차단 ${longHorizon.blockerCount}건</small>` : ""}
          <div class="ai-tournament-metrics">
            ${!isCostedLongHorizon ? `<span>점수 ${Number(row.score || 0).toFixed(2)}</span>` : `<span>총수익 ${longHorizon.totalLabel}</span>`}
            <span>MDD ${aiTournamentPct(row.max_drawdown_pct)}</span>
            <span>승률 ${aiTournamentPct(row.win_rate_pct, 1)}</span>
            <span>매매 ${Number(row.trade_count || 0).toLocaleString()}회</span>
            <span>${isCostedLongHorizon ? `SPY 대비 CAGR ${benchmarkCagrGap}` : `벤치마크 ${gap}`}</span>
            <span class="ai-tournament-grade">등급 ${escapeHtml(gate.grade || "-")} · 신뢰도 ${Number(gate.confidence_score || 0).toFixed(1)}</span>
            <span>${escapeHtml(gate.status || "게이트 대기")}${failedCount ? ` · 실패 ${failedCount}` : ""}</span>
            ${stress.status ? `<span class="${stress.passed ? "up" : "down"}">스트레스 ${escapeHtml(stress.status)} · P10 ${aiTournamentPct(stress.p10_return_pct)}</span>` : ""}
            ${contestRow ? `<span>${escapeHtml(contestRank.label || "실전대회")} ${Number(contestRow.estimated_rank)}등/${Number(contestRow.field_size)}명</span>` : ""}
          </div>
          ${aiTournamentTradeList(row.top_trades, "수익 TOP")}
          ${aiTournamentTradeList(row.bottom_trades, "손실 복기")}
        </article>
      `;
    }).join("") : errors.length ? errors.map((row) => `
      <article>
        <div class="ai-tournament-rank-head">
          <strong>${escapeHtml(aiTournamentStaffName(row))}</strong>
          <span class="down">실패</span>
        </div>
        <p>${escapeHtml(row.error || "완주하지 못했습니다.")}</p>
      </article>
    `).join("") : `<article><strong>순위표 대기</strong><p>미니리그를 실행하면 직원별 성과표가 여기에 표시됩니다.</p></article>`;
  }

  const lessonsNode = el("#aiTournamentLessons");
  if (lessonsNode) {
    const lessons = Array.isArray(run.lessons) ? run.lessons : [];
    const nextRules = Array.isArray(run.next_rules) ? run.next_rules : [];
    const errorLesson = errors.length ? [`이번 리그는 ${errors.length}명이 완주하지 못했습니다. 기간을 최소 40거래일 이상으로 늘리거나 종목을 바꿔 다시 실행하세요.`] : [];
    lessonsNode.innerHTML = `
      <strong>리그 복기</strong>
      ${(lessons.length ? lessons : errorLesson.length ? errorLesson : ["아직 복기할 리그 결과가 없습니다."]).map((item) => `<p>${escapeHtml(item)}</p>`).join("")}
      ${nextRules.length ? `<strong>다음 시즌 규칙</strong>${nextRules.map((item) => `<p>${escapeHtml(item)}</p>`).join("")}` : ""}
    `;
  }
}

function renderAiTournamentStandings(payload = {}) {
  const standings = Array.isArray(payload.standings) ? payload.standings : [];
  const meta = el("#aiTournamentStandingsMeta");
  if (meta) {
    const claimSummary = payload.return_claim_summary || {};
    meta.textContent = standings.length
      ? payload.refreshing
        ? `누적 ${Number(payload.run_count || 0)}개 대회 · ${standings.length}명 표시 · 공식 검증 갱신 중`
        : `누적 ${Number(payload.run_count || 0)}개 대회 · 공식검증 ${Number(claimSummary.trusted_run_count || 0)}건 · 참고전용 ${Number(claimSummary.quarantined_run_count || 0)}건`
      : "집계 대기";
  }
  const node = el("#aiTournamentStandings");
  if (!node) return;
  node.innerHTML = standings.length ? standings.map((row) => `
    <article class="${Number(row.standing_rank || 0) === 1 ? "is-leader" : ""} ${aiTournamentNeedsPriceReview(row) || row.return_claim_status === "review_required" ? "needs-price-review" : ""}">
      <div class="ai-tournament-rank-head">
        <strong>${Number(row.standing_rank || 0)}위 · ${escapeHtml(aiTournamentStaffName(row))}</strong>
        ${aiTournamentTrustedReturnBadge(row)}
      </div>
      <p>${escapeHtml(aiTournamentStaffProfile(row))} · ${escapeHtml((row.strategy_names || []).join(", ") || "-")}</p>
      <div class="ai-tournament-metrics">
        <span>누적 시즌 ${Number(row.activity_seasons ?? row.seasons ?? 0)}회</span>
        <span>훈련 우승 ${Number(row.activity_wins ?? row.wins ?? 0)}회</span>
        <span>공식 우승 ${Number(row.trusted_win_count || 0)}회</span>
        <span>공식 검증 ${Number(row.trusted_run_count || 0)}회</span>
        <span>참고 전용 ${Number(row.quarantined_run_count || 0)}회</span>
        <span>훈련 입상 ${Number(row.activity_podiums ?? row.podiums ?? 0)}회</span>
        <span>26년 CAGR ${row.long_horizon_2000_2026 ? aiTournamentLongHorizonClaim(row.long_horizon_2000_2026).cagrLabel : "-"}</span>
        <span>26년 총수익 ${row.long_horizon_2000_2026 ? aiTournamentLongHorizonClaim(row.long_horizon_2000_2026).totalLabel : "-"}</span>
        <span>26년 S&amp;P대비 ${row.long_horizon_2000_2026?.goal_evaluation?.excess_cagr_pctp !== undefined ? `${aiTournamentPct(row.long_horizon_2000_2026.goal_evaluation.excess_cagr_pctp)}p` : "-"}</span>
        <span>26년 검증 ${row.long_horizon_2000_2026 ? `${aiTournamentLongHorizonClaim(row.long_horizon_2000_2026).statusLabel} · 증거 ${aiTournamentLongHorizonClaim(row.long_horizon_2000_2026).confidence.toFixed(1)}점` : "미실행"}</span>
        <span>장기 목표 ${row.long_horizon_2000_2026?.goal_evaluation?.production_goal_pass ? "합격" : "미달"}</span>
        <span class="ai-tournament-realistic">비용후순위 ${Number(row.realism_standing_rank || 0) || "-"}위</span>
        <span>${aiTournamentOfficialReturnLabel(row)}</span>
        <span>${aiTournamentOfficialBestLabel(row)}</span>
        <span>참고용 원기록 평균 ${aiTournamentPct(row.avg_return_pct)}</span>
        <span>연평균 ${aiTournamentPct(row.avg_annualized_return_pct)}</span>
        <span class="ai-tournament-realistic">비용차감후 ${aiTournamentPct(row.avg_realistic_return_pct)}</span>
        <span class="ai-tournament-realistic">보수보정연평균 ${aiTournamentPct(row.avg_confidence_adjusted_annualized_pct)}</span>
        <span>비용차감 ${Number(row.avg_realism_cost_drag_pct || 0).toFixed(1)}%p</span>
        <span>평균투입 ${Number(row.avg_realism_allocation_pct || 0).toFixed(1)}%</span>
        <span>청산매매 ${Number(row.total_closed_trades || 0).toLocaleString()}회</span>
        <span>지수대비 ${aiTournamentPct(row.index_gap_annualized_pct)}p</span>
        <span>보정지수대비 ${aiTournamentPct(row.realistic_index_gap_annualized_pct)}p</span>
        <span>평균MDD ${aiTournamentPct(row.avg_drawdown_pct)}</span>
        <span>평균점수 ${Number(row.avg_score || 0).toFixed(2)}</span>
        <span>위험효율 ${Number(row.risk_efficiency || 0).toFixed(3)}</span>
        <span>비용후효율 ${Number(row.realistic_risk_efficiency || 0).toFixed(3)}</span>
      </div>
      <small class="ai-tournament-formula">${escapeHtml(row.return_claim_note || "공식 성과 주장은 수익률 대사 통과 기록만 사용합니다.")}</small>
      <small>최근 훈련순위 ${Number(row.latest_reference_rank ?? row.latest_rank ?? 0) || "-"}위 · 최근 훈련수익 ${aiTournamentPct(row.latest_reference_return_pct ?? row.latest_return_pct)} · 최근 대사상태 ${escapeHtml(row.latest_return_claim_status || "대기")} · 최근 비용차감후 ${aiTournamentPct(row.latest_realistic_return_pct)} · ${escapeHtml(row.latest_realism_grade || "검증등급 대기")} · 누적 매매 ${Number(row.activity_total_trades ?? row.total_trades ?? 0).toLocaleString()}회</small>
      <small class="ai-tournament-warning">훈련 횟수·원 우승·원기록 평균은 활동 이력입니다. 공식 순위와 성과는 수익률 대사 및 수수료·세금·슬리피지 검증을 모두 통과한 기록만 사용합니다.</small>
      ${row.improvement_plan ? `
        <div class="ai-tournament-improvement">
          <b>${escapeHtml(row.improvement_plan.gate || "개선 계획")}</b>
          <small>${escapeHtml(row.improvement_plan.role || "다음 훈련 역할 대기")}</small>
          ${(Array.isArray(row.improvement_plan.strengths) ? row.improvement_plan.strengths.slice(0, 2) : []).map((item) => `<span class="is-strength">${escapeHtml(item)}</span>`).join("")}
          ${(Array.isArray(row.improvement_plan.tasks) ? row.improvement_plan.tasks.slice(0, 4) : []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
        </div>
      ` : ""}
    </article>
  `).join("") : `<article><strong>누적 전적 대기</strong><p>왕중왕전 리그가 쌓이면 직원별 승률과 평균 성과가 여기에 표시됩니다.</p></article>`;
  const periodSummaries = Array.isArray(payload.period_summaries) ? payload.period_summaries : [];
  if (standings.length && periodSummaries.length) {
    node.insertAdjacentHTML("beforeend", `
      <article class="ai-tournament-period-summary">
        <div class="ai-tournament-rank-head">
          <strong>구간별 평균 수익률</strong>
          <span>검증 통과 기준</span>
        </div>
        <div class="ai-tournament-period-grid">
          ${periodSummaries.map((period) => `
            <div class="${Number(period.excluded_count || 0) ? "needs-price-review" : ""}">
              <b>${escapeHtml(period.period || "-")}</b>
              <span>평균수익 ${aiTournamentPct(period.avg_return_pct)}</span>
              <span>연평균 ${aiTournamentPct(period.avg_annualized_return_pct)}</span>
              <span>비용차감후 ${aiTournamentPct(period.avg_realistic_return_pct)}</span>
              <span>보수보정연평균 ${aiTournamentPct(period.avg_confidence_adjusted_annualized_pct)}</span>
              <span>비용차감 ${Number(period.avg_realism_cost_drag_pct || 0).toFixed(1)}%p</span>
              <span>지수대비 ${aiTournamentPct(period.index_gap_annualized_pct)}p</span>
              <span>보정지수대비 ${aiTournamentPct(period.realistic_index_gap_annualized_pct)}p</span>
              <small>통과 ${Number(period.verified_count || 0)}건 · 제외 ${Number(period.excluded_count || 0)}건 · 최고 ${escapeHtml(period.best_staff_name || "-")} ${aiTournamentPct(period.best_return_pct)}</small>
            </div>
          `).join("")}
        </div>
      </article>
    `);
  }
}

function renderAiStaffLearningAudit(payload = {}) {
  const rows = Array.isArray(payload.staff) ? payload.staff : [];
  const meta = el("#aiStaffLearningMeta");
  if (meta) {
    meta.textContent = rows.length
      ? `성장 증명 ${Number(payload.growth_proven_staff_count || 0)}/${rows.length}명 · 검증 학습 ${Number(payload.validated_learning_pair_count || 0)}쌍 · 개선 ${Number(payload.improved_learning_pair_count || 0)}쌍 · 출처 오류 ${Number(payload.invalid_provenance_count || 0)}건`
      : "검증 기록 대기";
  }
  const node = el("#aiStaffLearningAudit");
  if (!node) return;
  node.innerHTML = rows.length ? rows.map((row) => {
    const pairs = Array.isArray(row.learning_pairs) ? row.learning_pairs : [];
    const latestPair = pairs.length ? pairs[pairs.length - 1] : null;
    const improvement = latestPair?.risk_adjusted_improvement;
    return `
      <article class="${row.growth_proven ? "is-leader" : ""} ${Number(row.invalid_provenance_count || 0) ? "needs-price-review" : ""}">
        <div class="ai-tournament-rank-head">
          <strong>${escapeHtml(row.display_name || row.contestant_id || "AI 직원")}</strong>
          <span class="${row.growth_proven ? "up" : "down"}">${escapeHtml(row.growth_status || "검증 대기")}</span>
        </div>
        <p>${escapeHtml(row.diagnosis || "학습 전후 검증 기록이 아직 없습니다.")}</p>
        <div class="ai-tournament-metrics">
          <span>전체 훈련 ${Number(row.run_count || 0)}회</span>
          <span>공식 훈련 ${Number(row.trusted_run_count || 0)}회</span>
          <span>전략 변화 ${Number(row.trusted_strategy_transition_count || 0)}회</span>
          <span>인과 검증 ${Number(row.validated_learning_pair_count || 0)}쌍</span>
          <span class="up">개선 ${Number(row.improved_learning_pair_count || 0)}쌍</span>
          <span class="down">악화 ${Number(row.regressed_learning_pair_count || 0)}쌍</span>
          <span>출처 오류 ${Number(row.invalid_provenance_count || 0)}건</span>
          <span>평균 위험조정 개선 ${row.avg_risk_adjusted_improvement === null || row.avg_risk_adjusted_improvement === undefined ? "-" : Number(row.avg_risk_adjusted_improvement).toFixed(2)}</span>
        </div>
        ${latestPair ? `<small>최근 연결 ${escapeHtml(latestPair.source_record_id || "-")} → ${escapeHtml(latestPair.target_record_id || "-")} · ${escapeHtml(latestPair.status || "대기")}${improvement === undefined ? "" : ` · 개선 ${Number(improvement).toFixed(2)}`}</small>` : ""}
        <small class="ai-tournament-warning">반복 횟수나 전략 이름 변경만으로는 성장으로 인정하지 않습니다. 비용 차감 후 비중복 기간 성과가 실제 개선돼야 합니다.</small>
      </article>
    `;
  }).join("") : `<article><strong>학습 효과 검증 대기</strong><p>공식 검증을 통과한 두 개 이상의 비중복 훈련 구간이 필요합니다.</p></article>`;
}

function renderAiStaffDecisionReflectionAudit(payload = {}) {
  const rows = Array.isArray(payload.staff) ? payload.staff : [];
  const reflected = payload.next_decision_reflection_verified === true;
  const performanceProven = payload.performance_improvement_proven === true;
  const blockedRepeats = Number(payload.historical_regressed_repeat_opportunity_count || 0);
  setText(
    "aiStaffDecisionReflectionMeta",
    `${reflected ? "판단 반영 검증" : "판단 반영 점검"} · 실패 반복 ${blockedRepeats}건 차단 · ${performanceProven ? "성과 증명" : "성과 증명 대기"}`,
  );
  const node = el("#aiStaffDecisionReflectionAudit");
  if (!node) return;
  const stats = payload.effect_statistics && typeof payload.effect_statistics === "object"
    ? payload.effect_statistics
    : {};
  const confidenceLow = stats.confidence_interval_low;
  node.innerHTML = `
    <article class="${reflected ? "is-leader" : "needs-price-review"}">
      <div class="ai-tournament-rank-head">
        <strong>${reflected ? "학습 결과가 다음 판단에 반영됨" : "다음 판단 반영 경로 점검 필요"}</strong>
        <span class="${performanceProven ? "up" : "down"}">${performanceProven ? "성과 개선 증명" : "성과 개선 미증명"}</span>
      </div>
      <p>${reflected
        ? `새 전략 ID로 숨은 동일 실패 변형까지 찾아 과거 반복 기회 ${blockedRepeats}건을 전부 차단합니다.`
        : "이전 반사실 결과가 다음 전략 선택에 실제 반영되는지 확인이 필요합니다."}</p>
      <div class="ai-tournament-metrics">
        <span>인과 비교 ${Number(payload.causal_completed_triplet_count || 0)}개</span>
        <span class="up">개선 ${Number(payload.improved_triplet_count || 0)}개</span>
        <span class="down">퇴보 ${Number(payload.regressed_triplet_count || 0)}개</span>
        <span>유보 ${Number(payload.inconclusive_triplet_count || 0)}개</span>
        <span>평균 개선 ${stats.mean_risk_adjusted_improvement === null || stats.mean_risk_adjusted_improvement === undefined ? "-" : Number(stats.mean_risk_adjusted_improvement).toFixed(2)}</span>
        <span>95% 하한 ${confidenceLow === null || confidenceLow === undefined ? "-" : Number(confidenceLow).toFixed(2)}</span>
      </div>
      <small class="ai-tournament-warning">판단 반영 검증과 수익 개선 증명은 별개입니다. 95% 신뢰구간 하한이 0을 넘기 전에는 공식 성과나 실전 승격으로 인정하지 않습니다.</small>
    </article>
    ${rows.map((row) => `
      <article class="${row.no_unsafe_known_regressed_repeat ? "" : "needs-price-review"}">
        <div class="ai-tournament-rank-head">
          <strong>${escapeHtml(row.display_name || row.contestant_id || "AI 직원")}</strong>
          <span>${escapeHtml(row.feedback_decision || "판단 대기")}</span>
        </div>
        <small>과거 인과 비교 ${Number(row.prior_triplet_count || 0)}개 · 거절 서명 ${Number(row.rejected_signature_count || 0)}개 · 지지 서명 ${Number(row.supported_signature_count || 0)}개</small>
      </article>
    `).join("")}
  `;
}

async function loadAiStaffLearningAudit(log = false) {
  try {
    const response = await fetch("/api/ai-tournament/staff-learning-audit?limit=300");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "AI 직원 학습 효과 조회 실패");
    renderAiStaffLearningAudit(result);
    try {
      const reflectionResponse = await fetch("/api/ai-tournament/staff-learning-decision-reflection-audit");
      const reflection = await reflectionResponse.json();
      if (!reflectionResponse.ok) throw new Error(reflection.error || "다음 판단 반영 감사 실패");
      renderAiStaffDecisionReflectionAudit(reflection);
    } catch (reflectionError) {
      setText("aiStaffDecisionReflectionMeta", "감사 조회 실패");
      const reflectionNode = el("#aiStaffDecisionReflectionAudit");
      if (reflectionNode) reflectionNode.innerHTML = `<article><strong>다음 판단 반영 감사 실패</strong><p>${escapeHtml(reflectionError.message)}</p></article>`;
    }
    if (log) addLog("AI 직원 학습 효과 검증 조회");
  } catch (error) {
    setText("aiStaffLearningMeta", "검증 실패");
    const node = el("#aiStaffLearningAudit");
    if (node) node.innerHTML = `<article><strong>학습 효과 조회 실패</strong><p>${escapeHtml(error.message)}</p></article>`;
    addLog(`AI 직원 학습 효과 조회 실패: ${error.message}`);
  }
}

function aiTournamentAuditTradeList(trades = []) {
  const rows = Array.isArray(trades) ? trades.slice(0, 3) : [];
  if (!rows.length) return "";
  return `
    <div class="ai-tournament-trades">
      <b>핵심 매매</b>
      ${rows.map((trade) => `
        <span class="${aiTournamentNeedsPriceReview(trade) ? "needs-price-review" : ""}">
          ${escapeHtml(trade.label || pointInTimeDisplayName(trade.symbol, trade.entry_date || trade.date || trade.name_as_of_date, trade) || trade.name || trade.symbol || "-")}
          · ${escapeHtml(trade.entry_date || "-")}~${escapeHtml(trade.exit_date || "-")}
          · ${aiTournamentPct(trade.pnl_pct)}
          ${aiTournamentPriceReviewBadge(trade)}
        </span>
      `).join("")}
    </div>
  `;
}

function aiTournamentAuditRecordCard(row = {}, label = "기록") {
  const symbols = Array.isArray(row.selected_symbols) ? row.selected_symbols.slice(0, 8).join(", ") : "-";
  const targets = Array.isArray(row.beaten_targets) && row.beaten_targets.length
    ? row.beaten_targets.map((target) => `${target.name || "대상"} ${aiTournamentPct(target.return_pct)}`).join(", ")
    : Array.isArray(row.targets) && row.targets.length
      ? row.targets.slice(0, 2).map((target) => `${target.name || "대상"} ${aiTournamentPct(target.return_pct)}`).join(", ")
      : "";
  const priceReview = aiTournamentNeedsPriceReview(row);
  return `
    <article class="${priceReview ? "needs-price-review" : ""}">
      <small>${escapeHtml(label)} · ${escapeHtml(row.period || "-")}</small>
      <div class="ai-tournament-rank-head">
        <strong>${escapeHtml(row.staff_name || row.display_name || "-")}</strong>
        <span class="${Number(row.return_pct || 0) >= 0 ? "up" : "down"}">${aiTournamentPct(row.return_pct)}</span>
      </div>
      <p>${escapeHtml(row.strategy_name || row.strategy_mode || "-")} · 목표 ${aiTournamentPct(row.target_max_return_pct)} · 차이 ${aiTournamentPct(row.gap_pct)}p</p>
      <small>종목: ${escapeHtml(symbols || "-")}</small>
      ${row.reconciliation?.status ? `<small>수익률 대사: ${escapeHtml(row.reconciliation.status)} · ${escapeHtml(row.reconciliation.summary || "")}</small>` : ""}
      ${targets ? `<small>비교 대상: ${escapeHtml(targets)}</small>` : ""}
      <div class="ai-tournament-metrics">
        <span>MDD ${aiTournamentPct(row.mdd_pct)}</span>
        <span>승률 ${aiTournamentPct(row.win_rate_pct, 1)}</span>
        <span>매매 ${Number(row.trade_count || 0).toLocaleString()}회</span>
        <span>${row.beat_all ? "비교 대상 전부 초과" : `초과 ${Number(row.beat_count || 0)}개`}</span>
        ${priceReview ? aiTournamentPriceReviewBadge(row) : ""}
      </div>
      ${aiTournamentAuditTradeList(row.top_trades)}
    </article>
  `;
}

function renderAiTournamentChampionAudit(payload = {}) {
  const official = payload.official || {};
  const manual = payload.manual_benchmark || {};
  const legend = payload.internal_legend || {};
  const trusted = payload.trusted_summary || {};
  const priceRecon = payload.price_reconciliation || {};
  const exitRecon = payload.exit_reason_reconciliation || {};
  const summary = payload.summary || {};
  const reconciliationAudit = payload.return_reconciliation_audit || {};
  const reconciliationSummary = reconciliationAudit.summary || {};
  const priceQuarantined = Number(priceRecon.quarantined_run_count || trusted.price_quarantined_runs || 0);
  const claimBlocked = Number(exitRecon.claim_blocked_run_count || trusted.exit_reason_claim_blocked_runs || 0);
  const byStaff = Array.isArray(payload.by_staff) ? payload.by_staff : Array.isArray(payload.staff) ? payload.staff : [];
  const officialWins = Array.isArray(official.wins) ? official.wins : [];
  const closest = Array.isArray(official.closest_attempts) ? official.closest_attempts : [];
  const manualTop = Array.isArray(manual.top_benchmark_wins) ? manual.top_benchmark_wins : [];
  const legends = Array.isArray(legend.records) ? legend.records : Array.isArray(payload.trusted_legends) ? payload.trusted_legends : [];
  const quarantinedLegends = Array.isArray(payload.quarantined_legends) ? payload.quarantined_legends : [];
  const auditHeadline = payload.headline || (
    reconciliationSummary.status
      ? `수익률 대사 상태: ${reconciliationSummary.status}. 공식 성과는 전체 원장 대사가 통과한 기록만 사용합니다.`
      : "공식/수동/전설 기록을 실제 가격 검증 기준으로 분리했습니다."
  );
  const meta = el("#aiTournamentAuditMeta");
  if (meta) {
    meta.textContent = [
      `상태 ${payload.status || reconciliationSummary.status || "-"}`,
      `공식승리 ${Number(official.win_rows || summary.trusted_official_win_rows || 0)}건`,
      `수동벤치 ${Number(manual.top_benchmark_win_rows || 0)}건`,
      `전설 ${Number(legend.record_count || summary.legend_count || 0)}건`,
      `격리전설 ${Number(summary.quarantined_legend_count || quarantinedLegends.length || 0)}건`,
      `대사 ${Number(reconciliationSummary.rows_with_summary || 0)}건`,
      `샘플검산 ${Number(reconciliationSummary.legacy_sample_rows || 0)}건`,
      `가격격리 ${priceQuarantined}건`,
      `청산차단 ${claimBlocked}건`,
    ].join(" · ");
  }
  const node = el("#aiTournamentChampionAudit");
  if (!node) return;
  const officialCards = officialWins.length
    ? officialWins.slice(0, 3).map((row) => aiTournamentAuditRecordCard(row, "공식 챔피언 초과")).join("")
    : closest.slice(0, 2).map((row) => aiTournamentAuditRecordCard(row, "공식 챔피언 근접")).join("");
  const manualCards = manualTop.slice(0, 3).map((row) => aiTournamentAuditRecordCard(row, "수동 벤치마크 초과")).join("");
  const legendCards = legends.slice(0, 2).map((row) => aiTournamentAuditRecordCard(row, "검증 통과 전설")).join("");
  const quarantinedLegendCards = quarantinedLegends.slice(0, 3).map((row) => aiTournamentAuditRecordCard(row, "검토 필요 전설")).join("");
  const staffCards = byStaff.slice(0, 4).map((row) => `
    <article class="ai-tournament-staff-total-card">
      <small>직원별 누적</small>
      <div class="ai-tournament-rank-head">
        <strong>${escapeHtml(row.staff_name || row.display_name || "-")}</strong>
        <span>${aiTournamentPct(row.trusted_best_return_pct ?? row.best_return_pct)}</span>
      </div>
      <div class="ai-tournament-metrics">
        <span>공식 ${Number(row.official_champion_wins || row.trusted_official_wins || 0)}개</span>
        <span>격리공식 ${Number(row.quarantined_official_wins || 0)}건</span>
        <span>전설 ${Number(row.legend_records || 0)}건</span>
        <span>격리전설 ${Number(row.quarantined_legend_records || 0)}건</span>
      </div>
    </article>
  `).join("");
  node.innerHTML = `
    <article class="ai-tournament-audit-summary">
      <small>왕중왕전 감사 기준</small>
      <strong>검증 통과 기록만 공식 승리/전설로 인정</strong>
      <p>${escapeHtml(auditHeadline)}</p>
    </article>
    ${officialCards || `<article><strong>공식 챔피언 승리 없음</strong><p>현재 검증 통과 기준으로 공식 챔피언을 넘은 기록은 없습니다.</p></article>`}
    ${manualCards}
    ${legendCards}
    ${quarantinedLegendCards}
    <section class="ai-tournament-audit-staff-grid">${staffCards || `<article class="ai-tournament-staff-total-card"><strong>직원별 누적 대기</strong><p>직원별 누적 기록이 쌓이면 4개 카드가 같은 폭으로 표시됩니다.</p></article>`}</section>
  `;
}

async function loadAiTournamentChampionAudit(log = false) {
  try {
    const response = await fetch("/api/ai-tournament/champion-audit?limit=300");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "한투 챔피언 감사 조회 실패");
    renderAiTournamentChampionAudit(result);
    if (log) addLog("한투 챔피언 감사판 조회");
  } catch (error) {
    setText("aiTournamentAuditMeta", "감사 실패");
    const node = el("#aiTournamentChampionAudit");
    if (node) node.innerHTML = `<article><strong>챔피언 감사 조회 실패</strong><p>${escapeHtml(error.message)}</p></article>`;
    addLog(`한투 챔피언 감사 조회 실패: ${error.message}`);
  }
}

function renderAiStaffPersonas(payload = {}) {
  const rows = Array.isArray(payload.contestants) ? payload.contestants : [];
  const node = el("#aiStaffPersonaForm");
  if (!node) return;
  setText("aiStaffPersonaState", rows.length ? "수정 가능" : "기본 이름");
  const staffNames = rows.map((row) => aiTournamentStaffName(row).split(" · ")[0]).filter(Boolean).join(", ");
  setText("aiStaffPersonaIntro", `${staffNames || "AI 직원들"}이 같은 기간, 같은 자금, 같은 종목으로 과거장 Paper 리그를 치릅니다. 실전 주문은 절대 호출하지 않고 훈련 기록만 남깁니다.`);
  node.innerHTML = rows.map((row) => `
    <article class="ai-staff-persona-row" data-persona-id="${escapeHtml(row.id || "")}">
      <strong>${escapeHtml(row.name || row.id || "AI 직원")}</strong>
      <label><span>이름</span><input data-persona-field="persona_name" value="${escapeHtml(row.persona_name || "")}" /></label>
      <label><span>별명</span><input data-persona-field="call_sign" value="${escapeHtml(row.call_sign || "")}" /></label>
      <label><span>한 줄 역할</span><input data-persona-field="profile" value="${escapeHtml(row.profile || "")}" /></label>
    </article>
  `).join("");
}

async function loadAiStaffPersonas(log = false) {
  try {
    const response = await fetch("/api/ai-tournament/personas");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "직원 이름 설정 조회 실패");
    renderAiStaffPersonas(result);
    if (log) addLog("AI 직원 이름 설정 조회");
  } catch (error) {
    setText("aiStaffPersonaState", "조회 실패");
    addLog(`AI 직원 이름 설정 조회 실패: ${error.message}`);
  }
}

async function saveAiStaffPersonas() {
  const rows = Array.from(document.querySelectorAll(".ai-staff-persona-row")).map((row) => {
    const read = (field) => row.querySelector(`[data-persona-field="${field}"]`)?.value || "";
    return {
      id: row.dataset.personaId || "",
      persona_name: read("persona_name"),
      call_sign: read("call_sign"),
      profile: read("profile"),
    };
  });
  setText("aiStaffPersonaState", "저장 중");
  try {
    const response = await fetch("/api/ai-tournament/personas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ personas: rows, source: "web-ai-staff-persona" }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "직원 이름 저장 실패");
    renderAiStaffPersonas(result);
    await loadAiTournament(false);
    await loadAiTournamentStandings(false);
    setText("aiStaffPersonaState", "저장 완료");
    addLog("AI 직원 이름 설정 저장 완료");
  } catch (error) {
    setText("aiStaffPersonaState", "저장 실패");
    addLog(`AI 직원 이름 저장 실패: ${error.message}`);
  }
}

let aiTournamentStandingsRefreshTimer = null;

async function loadAiTournamentStandings(log = false) {
  try {
    const response = await fetch("/api/ai-tournament/standings?limit=100");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "AI 직원 전적표 조회 실패");
    renderAiTournamentStandings(result);
    if (aiTournamentStandingsRefreshTimer) clearTimeout(aiTournamentStandingsRefreshTimer);
    aiTournamentStandingsRefreshTimer = result.refreshing
      ? setTimeout(() => loadAiTournamentStandings(false), 10000)
      : null;
    await loadAiStaffLearningAudit(false);
    if (log) addLog("AI 직원 왕중왕전 누적 전적표 조회");
  } catch (error) {
    setText("aiTournamentStandingsMeta", "집계 실패");
    addLog(`AI 직원 왕중왕전 전적표 조회 실패: ${error.message}`);
  }
}

function aiTournamentQueryParams() {
  const params = new URLSearchParams({
    run: "1",
    name: "AI 직원 왕중왕전 미니리그",
    start: el("#aiTournamentStart")?.value || "2024-01-01",
    end: el("#aiTournamentEnd")?.value || todayIso(),
    cash: el("#aiTournamentCash")?.value || "100000000",
    symbols: el("#aiTournamentSymbols")?.value || "",
    selection: el("#aiTournamentSelection")?.value || "independent",
    contest_returns: el("#aiTournamentContestReturns")?.value || "",
    contest_label: "실전투자대회",
    champions: el("#aiTournamentUseChampions")?.checked ? "1" : "0",
    champion_id: el("#aiTournamentChampionPreset")?.value || "",
    source: "web-ai-tournament",
  });
  const benchmark = String(el("#aiTournamentBenchmark")?.value || "").trim();
  if (benchmark) params.set("benchmark_return", benchmark);
  return params;
}

async function loadAiTournament(log = false, includeAudits = log) {
  try {
    const response = await fetch("/api/ai-tournament/mini-league?limit=5");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "AI 직원 왕중왕전 조회 실패");
    renderAiTournamentScenarios(result.scenarios || []);
    await loadAiTournamentChampions(false);
    renderAiTournament(result);
    if (includeAudits) {
      await loadAiStaffPersonas(false);
      await loadAiTournamentStandings(false);
      await loadAiTournamentChampionAudit(false);
    }
    if (log) addLog("AI 직원 왕중왕전 최근 결과 조회");
  } catch (error) {
    setText("aiTournamentState", "조회 실패");
    addLog(`AI 직원 왕중왕전 조회 실패: ${error.message}`);
  }
}

async function runAiTournamentPhaseLeague() {
  applyAiTournamentPhaseToForm();
  state.aiTournamentRunning = true;
  renderAiTournament(state.lastAiTournament || {});
  setText("aiTournamentState", "구간 반복 실행 중");
  try {
    const params = new URLSearchParams({
      run: "1",
      phase: el("#aiTournamentPhase")?.value || "LEADER-2024",
      repeats: el("#aiTournamentRepeats")?.value || "3",
      cash: el("#aiTournamentCash")?.value || "100000000",
      selection: el("#aiTournamentSelection")?.value || "independent",
      contest_returns: el("#aiTournamentContestReturns")?.value || "",
      contest_label: "실전투자대회",
      champions: el("#aiTournamentUseChampions")?.checked ? "1" : "0",
      champion_id: el("#aiTournamentChampionPreset")?.value || "",
      source: "web-ai-phase-league",
    });
    const response = await fetch(`/api/ai-tournament/phase-league?${params.toString()}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "구간 반복 왕중왕전 실행 실패");
    const latestSeason = Array.isArray(result.seasons) ? result.seasons[result.seasons.length - 1] : null;
    if (latestSeason) renderAiTournament(latestSeason);
    await loadAiTournamentStandings(false);
    await loadAiTournamentChampionAudit(false);
    const leader = result.scoreboard?.[0]?.display_name || "-";
    addLog(`구간 반복 왕중왕전 완료: ${result.season_count || 0}시즌 · 최다 우승 ${leader}`);
    setText("aiTournamentState", `구간 반복 완료 · ${result.season_count || 0}시즌`);
  } catch (error) {
    setText("aiTournamentState", "구간 반복 실패");
    addLog(`구간 반복 왕중왕전 실패: ${error.message}`);
  } finally {
    state.aiTournamentRunning = false;
    renderAiTournament(state.lastAiTournament || {});
  }
}

async function runAiTournamentMini() {
  const startValue = el("#aiTournamentStart")?.value || "2024-01-01";
  const endValue = el("#aiTournamentEnd")?.value || todayIso();
  const startDate = new Date(startValue);
  const endDate = new Date(endValue);
  if (Number.isFinite(endDate - startDate) && (endDate - startDate) / 86400000 < 60) {
    setText("aiTournamentState", "기간 확인 필요");
    addLog("AI 직원 왕중왕전은 최소 40거래일 이상 필요합니다. 기간을 약 2개월 이상으로 잡아주세요.");
    return;
  }
  state.aiTournamentRunning = true;
  renderAiTournament(state.lastAiTournament || {});
  setText("aiTournamentState", "실행 중");
  try {
    const params = aiTournamentQueryParams();
    const response = await fetch(`/api/ai-tournament/mini-league?${params.toString()}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "AI 직원 미니리그 실행 실패");
    renderAiTournament(result);
    await loadAiTournamentStandings(false);
    await loadAiTournamentChampionAudit(false);
    addLog(`AI 직원 왕중왕전 완료: 챔피언 ${aiTournamentStaffName(result.champion || {})} · ${aiTournamentPct(result.champion?.total_return_pct)}`);
  } catch (error) {
    setText("aiTournamentState", "실행 실패");
    addLog(`AI 직원 왕중왕전 실행 실패: ${error.message}`);
  } finally {
    state.aiTournamentRunning = false;
    renderAiTournament(state.lastAiTournament || {});
  }
}

async function runMissionCycle() {
  setText("missionState", "미션 실행 중");
  try {
    const response = await fetch("/api/agent/mission/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "ui-mission" }),
    });
    const result = await response.json();
    const top = (result.cycle?.candidates || [])[0] || {};
    addLog(`AI 미션 실행 완료: ${top.symbol ? symbolDisplayName(top.symbol, top) : "-"} 점수 ${top.score || "-"}`);
    await loadMission();
    await loadOpsStatus();
    await loadScreener(false);
    await loadRadar(false);
    await loadAgentDaemon();
    await loadKrMarketAnalysis();
    await loadJournal();
    await loadWorklog();
    await loadPipeline();
    await loadAlerts();
  } catch (error) {
    setText("missionState", "실행 실패");
    addLog(`AI 미션 실행 실패: ${error.message}`);
  }
}

async function controlAgentDaemon(action) {
  const path = action === "start" ? "/api/agent/daemon/start" : action === "stop" ? "/api/agent/daemon/stop" : "/api/agent/daemon/run";
  setText("aiDaemonState", action === "run" ? "연구 실행 중" : "상태 변경 중");
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(action === "start" ? { interval_seconds: 10, source: "ui-continuous-research" } : { source: "ui" }),
    });
    const result = await response.json();
    if (result.cycle) {
      const top = (result.cycle.candidates || [])[0] || {};
      addLog(`AI 연구 1회 완료: ${top.symbol ? symbolDisplayName(top.symbol, top) : "-"} 점수 ${top.score || "-"}`);
    } else {
      addLog(`AI 데몬 ${action}: ${result.running ? "실행" : "정지"}`);
    }
    await loadAgentDaemon();
    await loadOpsStatus();
    await loadScreener(false);
    await loadRadar(false);
    await loadJournal();
    await loadWorklog();
    await loadPipeline();
    await loadAlerts();
  } catch (error) {
    addLog(`AI 데몬 제어 실패: ${error.message}`);
    setText("aiDaemonState", "오류");
  }
}

async function sendTelegramBrief() {
  const response = await fetch("/api/telegram/send-brief", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  const result = await response.json();
  addLog(`텔레그램 브리핑 outbox 등록: ${result.record?.id || "-"}`);
  await loadOpsStatus();
  await loadDispatchCenter();
  await loadAiBrief();
}

function renderCandidates(candidates) {
  const html = candidates.map((candidate, index) => `<div class="candidate"><strong>${index + 1}. ${candidate.name}</strong><small>\uc810\uc218 ${candidate.score} · \uac80\uc99d\uc218\uc775 ${candidate.test_return_pct}% · MDD ${candidate.test_drawdown_pct}% · \uc0e4\ud504 ${candidate.test_sharpe}</small></div>`).join("");
  el("#researchList").innerHTML = html;
  el("#dashCandidates").innerHTML = html || `<div class="event">${t.waiting}</div>`;
  setText("dashBestStrategy", candidates.length ? candidates[0].name : "-");
}

async function saveLogic() {
  const payload = { name: el("#logicName").value || "\ub098\uc758\uc804\ub7b5", fast: Number(el("#fast").value || 12), slow: Number(el("#slow").value || 32), memo: el("#logicMemo").value || "", locked: false };
  const response = await fetch("/api/logic/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "\ub85c\uc9c1 \uc800\uc7a5 \uc2e4\ud328");
  renderLogic(result.slots);
  addLog(`${t.saveLogic}: ${result.slot.name}`);
}

async function compareLogic() {
  const start = new Date(el("#startDate").value);
  const end = new Date(el("#endDate").value);
  const days = Number.isFinite(end - start) ? Math.max(60, Math.round((end - start) / 86400000)) : 260;
  const params = new URLSearchParams({ symbol: state.active, days, fast: el("#fast").value || 12, slow: el("#slow").value || 32 });
  const response = await fetch(`/api/compare?${params.toString()}`);
  const result = await response.json();
  if (!response.ok) return addLog(result.error || "\ub85c\uc9c1 \ube44\uad50 \uc2e4\ud328");
  setText("compareLine", `\uc0c1\uad00 ${result.correlation} · \uae30\uc900 ${result.base.total_return_pct}% · \ube44\uad50 ${result.candidate.total_return_pct}%`);
  addLog(`${t.compareLogic}: \uae30\uc900 ${result.base.total_return_pct}% / \ube44\uad50 ${result.candidate.total_return_pct}%`);
}

function addLog(message) {
  const now = new Date().toLocaleTimeString();
  resolveLatestButtonRunState(message);
  el("#eventLog").insertAdjacentHTML("afterbegin", `<div class="event"><strong>${now}</strong> ${productHtml(message)}</div>`);
}

let agentCommandPending = false;

function appendAgentMessage(role, text) {
  const body = el("#agentConsoleBody");
  if (!body) return null;
  const node = document.createElement("div");
  node.className = `agent-message ${role}`;
  node.textContent = text;
  body.appendChild(node);
  body.scrollTop = body.scrollHeight;
  return node;
}

async function sendAgentCommand(command) {
  const text = String(command || "").trim();
  if (!text || agentCommandPending) return;
  agentCommandPending = true;
  appendAgentMessage("user", text);
  const pendingMessage = appendAgentMessage("agent", "답변을 준비하고 있습니다. 잠시만 기다려주세요...");
  const sendButton = el("#agentCommandSend");
  const input = el("#agentCommandInput");
  const originalButtonText = sendButton?.textContent || "실행";
  if (sendButton) {
    sendButton.disabled = true;
    sendButton.textContent = "생성 중";
  }
  if (input) input.disabled = true;
  setText("agentConsoleState", "AI 답변 생성 중 · 보통 5~20초");
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 60_000);
  const startedAt = performance.now();
  try {
    const response = await fetch("/api/agent/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: text, source: "web-console" }),
      signal: controller.signal,
    });
    const raw = await response.text();
    let result = {};
    try {
      result = raw ? JSON.parse(raw) : {};
    } catch (_) {
      throw new Error(`서버 응답 형식 오류 (HTTP ${response.status})`);
    }
    if (!response.ok) throw new Error(result.error || result.reply || `HTTP ${response.status}`);
    if (pendingMessage) pendingMessage.textContent = result.reply || "응답 내용이 비어 있습니다.";
    const elapsedSeconds = Math.max(0.1, (performance.now() - startedAt) / 1000).toFixed(1);
    setText("agentConsoleState", result.ok ? `명령 완료 · ${elapsedSeconds}초` : "답변 확인 필요");
    addLog(`AI 명령: ${text}`);
  } catch (error) {
    const message = error?.name === "AbortError"
      ? "답변 생성이 60초를 넘겨 중단됐습니다. 다시 실행해주세요."
      : `명령 처리 실패: ${error.message}`;
    if (pendingMessage) pendingMessage.textContent = message;
    else appendAgentMessage("agent", message);
    setText("agentConsoleState", "오류");
  } finally {
    window.clearTimeout(timeoutId);
    agentCommandPending = false;
    if (sendButton) {
      sendButton.disabled = false;
      sendButton.textContent = originalButtonText;
    }
    if (input) {
      input.disabled = false;
      input.focus();
    }
  }
}

function externalEngineDashboardDeps() {
  return {
    setText,
    el,
    formatDateTimeShort,
    escapeHtml,
    koreanStatusText,
    addLog,
    fetchJson: window.fetch.bind(window),
  };
}

function renderExternalEngineDashboard(payload = {}) {
  const dashboard = window.CodexExternalEngineDashboard;
  if (!dashboard) throw new Error("외부 엔진 화면 모듈을 불러오지 못했습니다");
  return dashboard.render(payload, externalEngineDashboardDeps());
}

async function loadExternalEngineDashboard(silent = true) {
  const dashboard = window.CodexExternalEngineDashboard;
  if (!dashboard) throw new Error("외부 엔진 화면 모듈을 불러오지 못했습니다");
  return dashboard.load(silent, externalEngineDashboardDeps());
}

async function runExternalEngineImprovement() {
  const dashboard = window.CodexExternalEngineDashboard;
  if (!dashboard) throw new Error("외부 엔진 화면 모듈을 불러오지 못했습니다");
  return dashboard.runImprovement(externalEngineDashboardDeps());
}

async function loadAgentBrain() {
  try {
    const response = await fetch("/api/agent/staff/brain");
    const result = await response.json();
    const presets = result.presets || [];
    const roles = result.roles || {};
    const localModels = result.local_models || [];
    const modelOptions = el("#staffBrainModelOptions");
    if (modelOptions) {
      modelOptions.innerHTML = localModels.map((name) => `<option value="${escapeHtml(name)}"></option>`).join("");
    }
    ["operator", "researcher"].forEach((role) => renderStaffBrainRole(role, roles[role] || {}, presets));
    const operator = roles.operator?.config || {};
    setText("agentConsoleState", `운용 AI: ${operator.provider || "builtin"} / ${operator.model || "-"}`);
    setText("staffBrainState", result.message || "직원별 AI 모델 설정");
  } catch (error) {
    setText("staffBrainState", "AI 직원 모델 설정 확인 실패");
  }
}

function renderStaffBrainRole(role, row = {}, presets = []) {
  const config = row.config || {};
  const resolved = row.resolved || {};
  const provider = el(`#${role}BrainProvider`);
  if (provider) {
    provider.innerHTML = presets.map((preset) => `<option value="${escapeHtml(preset.id)}">${escapeHtml(preset.name)}</option>`).join("");
    provider.value = config.provider || "builtin";
  }
  const model = el(`#${role}BrainModel`);
  const endpoint = el(`#${role}BrainEndpoint`);
  if (model) model.value = config.model || "";
  if (endpoint) endpoint.value = config.endpoint || "";
  const runningModel = resolved.model && resolved.model !== config.model ? ` → 실행 ${resolved.model}` : "";
  const readyText = row.ready ? "준비됨" : "확인 필요";
  setText(`${role}BrainStatus`, readyText);
  setText(`${role}BrainResolved`, `${config.provider || "builtin"} / ${config.model || "-"}${runningModel}`);
}

async function saveStaffBrain(role) {
  const payload = {
    role,
    provider: el(`#${role}BrainProvider`)?.value || "builtin",
    model: el(`#${role}BrainModel`)?.value || "",
    endpoint: el(`#${role}BrainEndpoint`)?.value || "",
  };
  setText("staffBrainState", `${role === "operator" ? "운용" : "연구"} 직원 모델 저장 중`);
  try {
    const response = await fetch("/api/agent/staff/brain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    const config = result.config || payload;
    setText("staffBrainState", `${role === "operator" ? "운용/매매" : "연구"} 직원 모델 저장 완료`);
    addLog(`AI 직원 모델 저장: ${role === "operator" ? "운용/매매" : "연구"} · ${config.provider} / ${config.model || "-"}`);
    await loadAgentBrain();
    await loadAiStaff();
  } catch (error) {
    setText("staffBrainState", `AI 직원 모델 저장 실패: ${error.message}`);
  }
}

function syncStaffBrainPresetFields(role) {
  const providerId = el(`#${role}BrainProvider`)?.value;
  const optionText = el(`#${role}BrainProvider`)?.selectedOptions?.[0]?.textContent || "";
  const model = el(`#${role}BrainModel`);
  const endpoint = el(`#${role}BrainEndpoint`);
  const presets = {
    builtin: ["내장 규칙 엔진", ""],
    openai: ["gpt-4.1-mini", "https://api.openai.com/v1/chat/completions"],
    "ollama-local": ["qwen2.5:1.5b", "http://127.0.0.1:11434"],
    "ollama-gemma": ["gemma4:latest", "http://127.0.0.1:11434"],
    "ollama-qwen": ["qwen2.5:3b", "http://127.0.0.1:11434"],
    "ollama-llama": ["llama3.2:3b", "http://127.0.0.1:11434"],
    "ollama-deepseek": ["deepseek-r1:1.5b", "http://127.0.0.1:11434"],
    "ollama-phi": ["phi3:mini", "http://127.0.0.1:11434"],
    "custom-local": ["custom", "http://127.0.0.1:8000/generate"],
  };
  const preset = presets[providerId];
  if (!preset) return;
  if (model && (!model.value || optionText.includes("Ollama") || providerId === "builtin")) model.value = preset[0];
  if (endpoint && (!endpoint.value || providerId !== "custom-local")) endpoint.value = preset[1];
}

async function loadTelegramPollerStatus() {
  try {
    const response = await fetch("/api/telegram/poller");
    const status = await response.json();
    const running = Boolean(status.running && status.thread_alive);
    const label = running
      ? "텔레그램 자동감시 켜짐"
      : status.ready
        ? "텔레그램 자동감시 꺼짐"
        : "텔레그램 설정 확인 필요";
    const diagnostic = status.last_command_diagnostic || {};
    const diagnosticLabel = diagnostic.has_command
      ? ` · 최근 "${diagnostic.command || "-"}" ${diagnostic.sent_ok ? "전송완료" : "전송확인필요"}${diagnostic.retry_used ? " · 재시도" : ""}`
      : "";
    const displayLabel = running
      ? `텔레그램 자동감시 켜짐${diagnosticLabel}`
      : status.ready
        ? "텔레그램 자동감시 꺼짐"
        : "텔레그램 설정 확인 필요";
    if (!agentCommandPending) setText("agentConsoleState", displayLabel);
    const button = el("#agentPollTelegram");
    if (button) {
      button.textContent = "수동 확인";
      button.title = [
        displayLabel,
        status.last_error || status.reason || "",
        diagnostic.has_command ? `마지막 답변: ${diagnostic.reply_preview || "-"}` : "",
        diagnostic.has_command ? `전송: ${diagnostic.sent_ok ? "성공" : "확인 필요"} / 시도 ${diagnostic.attempt_count || 0}회 / ${diagnostic.dispatch_message || "-"}` : "",
      ].filter(Boolean).join("\n");
    }
  } catch (error) {
    if (!agentCommandPending) setText("agentConsoleState", "텔레그램 감시 상태 확인 실패");
  }
}

async function pollTelegramCommands() {
  setText("agentConsoleState", "텔레그램 수동 확인 중");
  try {
    const response = await fetch("/api/telegram/poll", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timeout: 0 }),
    });
    const result = await response.json();
    const handled = result.handled || [];
    if (!handled.length) {
      appendAgentMessage("agent", `텔레그램 새 명령 없음 (${result.message || "확인 완료"})`);
    } else {
      handled.forEach((item) => appendAgentMessage("agent", `텔레그램 명령 처리: ${item.command}\n${item.result?.reply || ""}`));
    }
    setText("agentConsoleState", `텔레그램 ${handled.length}건 처리`);
    await loadTelegramPollerStatus();
  } catch (error) {
    appendAgentMessage("agent", `텔레그램 확인 실패: ${error.message}`);
    setText("agentConsoleState", "텔레그램 오류");
  }
}

function bindAgentConsole() {
  const panel = el("#agentConsole");
  const head = el("#agentConsoleHead");
  const form = el("#agentCommandForm");
  const input = el("#agentCommandInput");
  if (!panel || !head || !form || !input) return;
  let dragging = false;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;

  head.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) return;
    dragging = true;
    const rect = panel.getBoundingClientRect();
    startX = event.clientX;
    startY = event.clientY;
    startLeft = rect.left;
    startTop = rect.top;
    panel.style.left = `${rect.left}px`;
    panel.style.top = `${rect.top}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    head.setPointerCapture(event.pointerId);
  });

  head.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const nextLeft = Math.min(window.innerWidth - 80, Math.max(0, startLeft + event.clientX - startX));
    const nextTop = Math.min(window.innerHeight - 58, Math.max(0, startTop + event.clientY - startY));
    panel.style.left = `${nextLeft}px`;
    panel.style.top = `${nextTop}px`;
  });

  head.addEventListener("pointerup", (event) => {
    dragging = false;
    try { head.releasePointerCapture(event.pointerId); } catch (_) {}
  });

  el("#agentConsoleMinimize").addEventListener("click", () => {
    panel.classList.toggle("minimized");
  });
  el("#agentPollTelegram").addEventListener("click", pollTelegramCommands);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const command = input.value;
    input.value = "";
    sendAgentCommand(command);
  });
}

function consolidateWorkspace() {
  const logicPage = el("#logic");
  const logicMount = el("#researchLogicMount");
  if (logicPage && logicMount && logicMount.dataset.merged !== "1") {
    Array.from(logicPage.children).forEach((child) => logicMount.appendChild(child));
    logicMount.dataset.merged = "1";
    logicPage.classList.add("merged-page-hidden");
  }

  const journalPage = el("#journal");
  const journalMount = el("#settingsJournalMount");
  const consolePanel = el("#agentConsole");
  if (consolePanel && consolePanel.dataset.detached !== "1") {
    document.body.appendChild(consolePanel);
    consolePanel.dataset.detached = "1";
  }
  if (journalPage && journalMount && journalMount.dataset.merged !== "1") {
    Array.from(journalPage.children).forEach((child) => {
      if (child.id !== "agentConsole") journalMount.appendChild(child);
    });
    journalMount.dataset.merged = "1";
    journalPage.classList.add("merged-page-hidden");
  }
}

let eventsBound = false;

function bindEvents() {
  if (eventsBound) return;
  consolidateWorkspace();
  window.CodexStockSubpages?.init();
  ensureStrategyChartControls();
  bindMainPriceChartControls();
  bindTabOrderControls();
  el("#appTitle").addEventListener("dblclick", beginAppNameEdit);
  el("#appTitle").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      finishAppNameEdit(true);
    }
    if (event.key === "Escape") {
      event.preventDefault();
      finishAppNameEdit(false);
    }
  });
  el("#appTitle").addEventListener("blur", () => finishAppNameEdit(true));
  el("#quantity")?.addEventListener("input", renderOrderPreview);
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", (event) => {
    if (tab.dataset.dragMoved === "1") {
      event.preventDefault();
      return;
    }
    switchPage(tab.dataset.page);
  }));
  document.querySelectorAll("[data-page-jump]").forEach((button) => button.addEventListener("click", () => switchPage(button.dataset.pageJump)));
  switchPage(document.querySelector(".page.active")?.id || "dashboard");
  document.querySelectorAll("[data-staff-brain-save]").forEach((button) => {
    button.addEventListener("click", () => saveStaffBrain(button.dataset.staffBrainSave));
  });
  el("#refreshExternalEngines")?.addEventListener("click", () => loadExternalEngineDashboard(false));
  el("#runExternalImprovement")?.addEventListener("click", () => runExternalEngineImprovement());
  el("#copyProgramIntro")?.addEventListener("click", copyProgramIntro);
  el("#downloadProgramIntro")?.addEventListener("click", downloadProgramIntro);
  el("#copyFriendReleaseCommand")?.addEventListener("click", copyFriendReleaseCommand);
  el("#copyFriendUsageGuide")?.addEventListener("click", copyFriendUsageGuide);
  el("#copyApiSetupGuide")?.addEventListener("click", copyApiSetupGuide);
  el("#copyReleaseReadinessSummary")?.addEventListener("click", copyReleaseReadinessSummary);
  el("#downloadReleaseReadinessSummary")?.addEventListener("click", downloadReleaseReadinessSummary);
  el("#copyFriendSharePack")?.addEventListener("click", copyFriendSharePack);
  el("#downloadFriendSharePack")?.addEventListener("click", downloadFriendSharePack);
  el("#refreshFriendReleaseReadiness")?.addEventListener("click", loadFriendReleaseReadiness);
  ["operator", "researcher"].forEach((role) => {
    el(`#${role}BrainProvider`)?.addEventListener("change", () => syncStaffBrainPresetFields(role));
  });
  document.querySelectorAll("[data-account-tab]").forEach((button) => button.addEventListener("click", () => {
    state.accountView = button.dataset.accountTab || "paper";
    renderAccountDashboard();
    if (state.accountView === "live" && !state.liveAccountSnapshot?.ok) loadKisAccount();
    if (state.accountView === "paper" && !state.lastOpsStatus) loadOpsStatus();
  }));
  el("#livePerformanceDateFilter")?.addEventListener("change", (event) => setLivePerformanceDateFilter(event.target.value));
  el("#livePerformanceToday")?.addEventListener("click", () => setLivePerformanceDateFilter(todayIso()));
  el("#livePerformanceAll")?.addEventListener("click", () => setLivePerformanceDateFilter(""));
  el("#refreshMaturityScore")?.addEventListener("click", () => loadCodexstockMaturity(false));
  el("#runConditionScreener")?.addEventListener("click", () => loadConditionScreener(false));
  el("#relaxConditionScreener")?.addEventListener("click", relaxConditionScreener);
  el("#refreshConditionScreenerHistory")?.addEventListener("click", () => loadConditionScreenerHistory(false));
  el("#refreshLiveDecisionContext")?.addEventListener("click", () => loadLiveDecisionContext(false));
  el("#refreshLiveDecisionContextDeep")?.addEventListener("click", () => loadLiveDecisionContext(false, { refresh: true }));
  el("#conditionAutoRefresh")?.addEventListener("change", updateConditionAutoRefresh);
  el("#conditionPreset")?.addEventListener("change", (event) => {
    applyConditionPresetValues(event.target.value);
    loadConditionScreener(false);
  });
  ["#conditionMarket", "#conditionMinAmount", "#conditionMinChange", "#conditionMaxChange", "#conditionMinPower", "#conditionMinBuyRate", "#conditionMaxSellRate", "#conditionMinScore"].forEach((selector) => {
    el(selector)?.addEventListener("change", () => {
      if (el("#conditionPreset")?.value !== "custom") el("#conditionPreset").value = "custom";
      loadConditionScreener(false);
    });
  });
  document.addEventListener("click", (event) => {
    const conditionSymbolButton = event.target.closest("[data-condition-symbol]");
    if (conditionSymbolButton) {
      event.preventDefault();
      event.stopPropagation();
      const symbol = String(conditionSymbolButton.dataset.conditionSymbol || "").toUpperCase();
      if (symbol) {
        state.active = symbol;
        state.equity = [];
        state.priceChart.symbol = "";
        if (el("#symbol")) el("#symbol").value = symbol;
        renderMarket();
        tickMarket(true).catch((error) => addLog(`조건검색 차트 갱신 실패: ${error.message}`));
        addLog(`조건검색 종목 선택: ${symbolDisplayName(symbol)} 차트로 이동했습니다.`);
      }
      return;
    }
    const guideButton = event.target.closest("[data-guide-button]");
    if (guideButton) {
      event.preventDefault();
      event.stopPropagation();
      const buttonId = guideButton.dataset.guideButton || "";
      highlightPilotTargetButton(buttonId);
      const target = document.getElementById(buttonId);
      if (target) showButtonHint(target);
      return;
    }
    const confirmCopyButton = event.target.closest("[data-copy-confirm-phrase]");
    if (confirmCopyButton) {
      event.preventDefault();
      event.stopPropagation();
      const phrase = confirmCopyButton.dataset.copyConfirmPhrase || "";
      copyTextToClipboard(phrase)
        .then(() => addLog(`확인문구를 복사했습니다: ${phrase}. 복사만 했고 실제 주문은 실행하지 않았습니다.`))
        .catch((error) => addLog(`확인문구 복사 실패: ${error.message}`));
      return;
    }
    const reasonBackfillButton = event.target.closest("#saveLiveReasonBackfill");
    if (reasonBackfillButton) {
      event.preventDefault();
      event.stopPropagation();
      saveLiveReasonBackfill();
      return;
    }
    const blackboxButton = event.target.closest("#saveLiveOrderBlackbox");
    if (blackboxButton) {
      event.preventDefault();
      event.stopPropagation();
      loadLiveOrderBlackbox({ persist: true, silent: false });
      return;
    }
    const reconciliationButton = event.target.closest("[data-refresh-reconciliation]");
    if (reconciliationButton) {
      event.preventDefault();
      event.stopPropagation();
      runLiveReconciliationCheck(false);
      return;
    }
    const orderStateButton = event.target.closest("[data-refresh-order-state]");
    if (orderStateButton) {
      event.preventDefault();
      event.stopPropagation();
      loadTradeBlockerSnapshot(false);
      return;
    }
    const runtimeStorageButton = event.target.closest("#runtimeStorageBackfill");
    if (runtimeStorageButton) {
      event.preventDefault();
      event.stopPropagation();
      runtimeStorageButton.disabled = true;
      runtimeStorageButton.textContent = "백필 중";
      fetch("/api/ops/storage/backfill?max_rows=120")
        .then((response) => response.json().then((result) => ({ response, result })))
        .then(({ response, result }) => {
          if (!response.ok || result.ok === false) throw new Error(result.error || result.message || "저장소 백필 실패");
          addLog(`SQLite 백필: 신규 ${Number(result.inserted || 0).toLocaleString()}건 / 중복 ${Number(result.skipped || 0).toLocaleString()}건 · ${Number(result.elapsed_ms || 0).toFixed(1)}ms`);
          renderRuntimeStorageCard(result.status || {});
          return loadOpsStatus();
        })
        .catch((error) => addLog(`SQLite 백필 실패: ${error.message}`))
        .finally(() => {
          const nextButton = el("#runtimeStorageBackfill");
          if (nextButton) {
            nextButton.disabled = false;
            nextButton.textContent = "SQLite 소규모 백필";
          }
        });
      return;
    }
    const externalKnowledgeButton = event.target.closest("#refreshExternalKnowledge");
    if (externalKnowledgeButton) {
      event.preventDefault();
      event.stopPropagation();
      loadExternalKnowledge(false);
      return;
    }
    const todayTradeInlineButton = event.target.closest("#refreshTodayTradesInline");
    if (todayTradeInlineButton) {
      event.preventDefault();
      event.stopPropagation();
      loadTodayTradeQuickSummary(false);
      return;
    }
    const livePerformancePageButton = event.target.closest("[data-live-performance-page]");
    if (livePerformancePageButton) {
      event.preventDefault();
      event.stopPropagation();
      setLivePerformancePage(livePerformancePageButton.dataset.livePerformancePage);
      return;
    }
    const brokerJournalButton = event.target.closest("#refreshBrokerJournal");
    if (brokerJournalButton) {
      event.preventDefault();
      event.stopPropagation();
      loadBrokerExecutionJournal(false);
      return;
    }
    const missedBuyButton = event.target.closest("#refreshMissedBuyReview");
    if (missedBuyButton) {
      event.preventDefault();
      event.stopPropagation();
      loadMissedBuyReview(false);
      return;
    }
    const competitiveButton = event.target.closest("#runCompetitiveAudit");
    if (competitiveButton) {
      event.preventDefault();
      event.stopPropagation();
      loadCompetitiveAudit(true, { depth: "standard" });
      return;
    }
    const competitiveFullButton = event.target.closest("#runCompetitiveAuditFull");
    if (competitiveFullButton) {
      event.preventDefault();
      event.stopPropagation();
      loadCompetitiveAudit(true, { depth: "full" });
      return;
    }
    const competitiveActionButton = event.target.closest("[data-competitive-button]");
    if (competitiveActionButton) {
      event.preventDefault();
      event.stopPropagation();
      goToCompetitiveAction(competitiveActionButton.dataset.competitivePage, competitiveActionButton.dataset.competitiveButton);
      return;
    }
    const watchSelectButton = event.target.closest("[data-watch-select]");
    if (watchSelectButton) {
      event.preventDefault();
      event.stopPropagation();
      chooseWatchlistSymbol(watchSelectButton.dataset.watchSelect);
      return;
    }
    const removeButton = event.target.closest("[data-watch-remove]");
    if (removeButton) {
      event.preventDefault();
      event.stopPropagation();
      saveWatchlistSymbol("remove", removeButton.dataset.watchRemove);
      return;
    }
    const addButton = event.target.closest("[data-watch-add]");
    if (addButton) {
      event.preventDefault();
      event.stopPropagation();
      saveWatchlistSymbol("add", addButton.dataset.watchAdd);
      return;
    }
    if (!event.target.closest(".watchlist-search-wrap")) closeWatchlistDropdown();
  });
  document.addEventListener("click", (event) => {
    const symbolButton = event.target.closest("[data-symbol]");
    if (!symbolButton) return;
    state.active = symbolButton.dataset.symbol;
    state.equity = [];
    state.priceChart.symbol = "";
    renderMarket();
    renderOrderPreview();
    tickMarket(true).catch((error) => addLog(`선택종목 데이터 갱신 실패: ${error.message}`));
    loadLivePilotPlan(true).catch((error) => addLog(`AI 후보 갱신 실패: ${error.message}`));
    addLog(`${symbolDisplayName(state.active)} ${t.selected} · 차트/감독석 동기화`);
  });
  document.addEventListener("click", (event) => {
    const optimizedButton = event.target.closest("[data-apply-optimized]");
    if (!optimizedButton) return;
    const [fast, slow] = String(optimizedButton.dataset.applyOptimized || "").split(",");
    if (fast && slow) {
      el("#fast").value = fast;
      el("#slow").value = slow;
      addLog(`최적화 파라미터 적용: MA ${fast}/${slow}`);
      runBacktest();
      runRobustness();
      runProtections();
    }
  });
  document.addEventListener("click", (event) => {
    const promoteButton = event.target.closest("[data-promote-validation]");
    if (!promoteButton) return;
    registerPromotionCandidate();
  });
  document.addEventListener("click", (event) => {
    const rehearsalButton = event.target.closest("[data-paper-rehearsal]");
    if (!rehearsalButton) return;
    createPromotionPaperRehearsal(rehearsalButton.dataset.paperRehearsal);
  });
  document.addEventListener("click", (event) => {
    const reportButton = event.target.closest("[data-queue-rehearsal-report]");
    if (!reportButton) return;
    queuePromotionRehearsalReport(reportButton.dataset.queueRehearsalReport);
  });
  document.addEventListener("click", (event) => {
    const digestButton = event.target.closest("[data-queue-rehearsal-digest]");
    if (!digestButton) return;
    queuePromotionRehearsalDigest();
  });
  document.addEventListener("click", (event) => {
    const trendButton = event.target.closest("[data-queue-rehearsal-trend]");
    if (!trendButton) return;
    queuePromotionRehearsalTrend();
  });
  document.addEventListener("click", (event) => {
    const snapshotButton = event.target.closest("[data-record-rehearsal-snapshot]");
    if (!snapshotButton) return;
    recordPromotionRehearsalSnapshot();
  });
  document.addEventListener("click", (event) => {
    const obsidianButton = event.target.closest("[data-save-rehearsal-obsidian]");
    if (!obsidianButton) return;
    savePromotionRehearsalObsidian();
  });
  document.addEventListener("click", (event) => {
    const pilotTargetButton = event.target.closest("[data-pilot-target-button]");
    if (!pilotTargetButton) return;
    highlightPilotTargetButton(pilotTargetButton.dataset.pilotTargetButton);
  });
  el("#runBacktest").addEventListener("click", runBacktest);
  el("#runMultiBacktest").addEventListener("click", runMultiBacktest);
  el("#runRobustness").addEventListener("click", runRobustness);
  el("#runProtections").addEventListener("click", runProtections);
  el("#runHistoricalReplay").addEventListener("click", runHistoricalReplay);
  el("#runDailyReplayDrill")?.addEventListener("click", runDailyReplayDrill);
  el("#replayStrategy").addEventListener("change", applyReplayStrategyDefaults);
  el("#replaySymbolSearch").addEventListener("input", (event) => renderReplaySymbolDropdown(event.target.value));
  el("#replaySymbolSearch").addEventListener("focus", (event) => renderReplaySymbolDropdown(event.target.value));
  el("#replaySymbolDropdown").addEventListener("wheel", (event) => event.stopPropagation(), { passive: true });
  el("#runValidationSuite").addEventListener("click", runValidationSuite);
  el("#validationScenario").addEventListener("change", applyValidationScenario);
  el("#runTranscriptStrategy").addEventListener("click", runTranscriptStrategy);
  el("#researchButton").addEventListener("click", runResearch);
  el("#liveResearchButton").addEventListener("click", runLiveResearch);
  el("#refreshAiBrief").addEventListener("click", loadAiBrief);
  el("#sendTelegramBrief").addEventListener("click", sendTelegramBrief);
  el("#smallAccountRefresh")?.addEventListener("click", () => refreshSmallAccountGrowth(true).catch(() => {}));
  el("#refreshPreMarketBrief").addEventListener("click", () => loadPreMarketBriefing(true));
  el("#queuePreMarketBrief").addEventListener("click", queuePreMarketBriefing);
  el("#analyzeKrMarket").addEventListener("click", loadKrMarketAnalysis);
  el("#watchlistAdd").addEventListener("click", addWatchlistFromInput);
  el("#watchlistAddActive").addEventListener("click", () => saveWatchlistSymbol("add", state.active));
  el("#watchlistSyncKis")?.addEventListener("click", () => syncKisWatchlist(false));
  el("#watchlistInput").addEventListener("input", (event) => renderWatchlistDropdown(event.target.value));
  el("#watchlistInput").addEventListener("focus", (event) => renderWatchlistDropdown(event.target.value));
  el("#watchlistInput").addEventListener("keydown", handleWatchlistSearchKeydown);
  el("#watchlistDropdown").addEventListener("wheel", (event) => event.stopPropagation(), { passive: true });
  el("#refreshRecommendations").addEventListener("click", () => loadRecommendations(true));
  el("#refreshOpportunities").addEventListener("click", () => loadOpportunities(true));
  el("#runMissionCycle").addEventListener("click", runMissionCycle);
  el("#runAutopilotTick").addEventListener("click", runAutopilotTick);
  el("#healthReportTelegram").addEventListener("click", queueHealthReport);
  el("#startAutopilotScheduler").addEventListener("click", () => controlAutopilotScheduler("start"));
  el("#stopAutopilotScheduler").addEventListener("click", () => controlAutopilotScheduler("stop"));
  el("#runScreener").addEventListener("click", () => loadScreener(true));
  el("#runSectorCommittee")?.addEventListener("click", () => loadSectorCommittee(true));
  el("#queueAlertDigest").addEventListener("click", queueAlertDigest);
  el("#dispatchTelegramReports").addEventListener("click", dispatchTelegramReports);
  el("#runDossier").addEventListener("click", () => runDossier());
  el("#dossierSymbol").addEventListener("input", () => { el("#dossierSymbol").dataset.touched = "1"; });
  el("#runRadar").addEventListener("click", () => loadRadar(true));
  el("#runSectorNews").addEventListener("click", () => loadSectorNews(true));
  el("#refreshCapitalChallenge")?.addEventListener("click", () => loadCapitalChallenge(false, { userAction: true }));
  el("#runCapitalChallenge")?.addEventListener("click", runCapitalChallenge);
  el("#copyCapitalSummary")?.addEventListener("click", copyCapitalSummary);
  el("#downloadCapitalSummary")?.addEventListener("click", downloadCapitalSummary);
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-capital-phase-train]");
    if (!button) return;
    runCapitalPhaseTraining(button.dataset.capitalPhaseTrain || "");
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-hundred-lab-show-all]");
    if (!button) return;
    state.hideHundredLabHighRisk = false;
    try {
      localStorage.setItem(HUNDRED_LAB_HIDE_RISK_STORAGE_KEY, "0");
    } catch (_) {}
    renderHundredBillionLab(state.lastHundredLabStatus || {});
    addLog("전략 후보 탐색기 전체 후보 다시 표시");
  });
  document.querySelectorAll("[data-hundred-lab-run]").forEach((button) => {
    button.addEventListener("click", () => runHundredBillionLab(button.dataset.hundredLabRun || "focus"));
  });
  el("#refreshHundredLab")?.addEventListener("click", () => loadHundredBillionLabStatus(true));
  el("#toggleHundredLabHideRisk")?.addEventListener("click", toggleHundredLabHideRisk);
  el("#toggleHundredLabEfficiencySort")?.addEventListener("click", toggleHundredLabEfficiencySort);
  el("#copyHundredLabTop")?.addEventListener("click", copyHundredLabTop);
  el("#downloadHundredLabTop")?.addEventListener("click", downloadHundredLabTop);
  el("#stopHundredLab")?.addEventListener("click", stopHundredBillionLab);
  el("#runAiTournamentMini")?.addEventListener("click", runAiTournamentMini);
  el("#runAiTournamentPhase")?.addEventListener("click", runAiTournamentPhaseLeague);
  el("#refreshAiTournament")?.addEventListener("click", () => loadAiTournament(true));
  el("#saveAiStaffPersonas")?.addEventListener("click", saveAiStaffPersonas);
  el("#aiTournamentPhase")?.addEventListener("change", applyAiTournamentPhaseToForm);
  el("#applyAiTournamentChampion")?.addEventListener("click", applyAiTournamentChampionCondition);
  el("#featureHealthRefresh")?.addEventListener("click", () => refreshFeatureHealth(true));
  el("#opsPaperBuy").addEventListener("click", createOpsPaperBuy);
  el("#opsLiveCandidate").addEventListener("click", createOpsLiveCandidate);
  el("#opsApproveLatest").addEventListener("click", approveLatestOps);
  el("#opsDrySubmit").addEventListener("click", drySubmitOps);
  el("#opsQueueTelegram").addEventListener("click", queueOpsTelegram);
  el("#pilotPlanRefresh").addEventListener("click", () => loadLivePilotPlan(false));
  el("#pilotPlanFullRefresh")?.addEventListener("click", () => loadLivePilotPlan(false, "", { full: true }));
  el("#pilotCreateCandidate").addEventListener("click", () => createLivePilotCandidate("BUY"));
  el("#pilotCreateSellCandidate").addEventListener("click", () => createLivePilotCandidate("SELL"));
  el("#pilotLiveSubmit").addEventListener("click", liveSubmitPilotOps);
  el("#refreshTradeBlockers")?.addEventListener("click", () => {
    loadTradeBlockerSnapshot(false);
    loadTodayTradeQuickSummary(true);
  });
  el("#refreshTodayTrades")?.addEventListener("click", () => loadTodayTradeQuickSummary(false));
  el("#refreshLiveAccountChanges")?.addEventListener("click", () => loadLiveAccountChanges(false));
  el("#refreshIntradayMinuteRadar")?.addEventListener("click", () => loadIntradayMinuteRadar(false));
  el("#refreshKisRankRadar")?.addEventListener("click", () => loadKisRankRadar(false));
  el("#kisRankRadarMarket")?.addEventListener("change", () => loadKisRankRadar(false));
  el("#refreshKisFluctuationRadar")?.addEventListener("click", () => loadKisFluctuationRadar(false));
  el("#kisFluctuationDirection")?.addEventListener("change", () => loadKisFluctuationRadar(false));
  el("#kisFluctuationMarket")?.addEventListener("change", () => loadKisFluctuationRadar(false));
  el("#refreshKisVolumePowerRadar")?.addEventListener("click", () => loadKisVolumePowerRadar(false));
  el("#kisVolumePowerMarket")?.addEventListener("change", () => loadKisVolumePowerRadar(false));
  el("#refreshKisQuoteBalanceRadar")?.addEventListener("click", () => loadKisQuoteBalanceRadar(false));
  el("#kisQuoteBalanceKind")?.addEventListener("change", () => loadKisQuoteBalanceRadar(false));
  el("#kisQuoteBalanceMarket")?.addEventListener("change", () => loadKisQuoteBalanceRadar(false));
  ["opsPolicyPilotCashPct", "opsPolicyAutoCashPct", "opsPolicyApprovalCashPct", "opsPolicyDynamicMaxCashPct"].forEach((id) => {
    el(`#${id}`)?.addEventListener("input", () => updateOpsCapitalRiskBadge(buildOpsPolicyPayload()));
  });
  el("#opsSavePolicy").addEventListener("click", saveOpsPolicy);
  el("#opsActive50Mode")?.addEventListener("click", applyActive50Policy);
  el("#opsAutoStart").addEventListener("click", startAutoTradeOps);
  el("#opsAutoStop").addEventListener("click", stopAutoTradeOps);
  el("#opsEmergencyStop").addEventListener("click", emergencyStopOps);
  el("#opsResume").addEventListener("click", resumeOps);
  el("#opsTargetPreview").addEventListener("click", loadPortfolioTargets);
  el("#opsApplyPaperTargets").addEventListener("click", applyPaperTargets);
  el("#aiTrainingToggle").addEventListener("click", toggleAiTraining);
  el("#startAiDaemon").addEventListener("click", () => controlAgentDaemon("start"));
  el("#runAiCycle").addEventListener("click", () => controlAgentDaemon("run"));
  el("#runQuickStaffMeeting")?.addEventListener("click", runQuickStaffMeeting);
  el("#stopAiDaemon").addEventListener("click", () => controlAgentDaemon("stop"));
  el("#saveLogicButton").addEventListener("click", saveLogic);
  el("#compareButton").addEventListener("click", compareLogic);
  el("#buyButton").addEventListener("click", () => submitOrder("BUY"));
  el("#sellButton").addEventListener("click", () => submitOrder("SELL"));
  el("#autoButton").addEventListener("click", runAutoStrategy);
  el("#refreshStatus").addEventListener("click", loadStatus);
  el("#refreshApiStatus").addEventListener("click", loadIntegrations);
  el("#clearLog").addEventListener("click", () => { el("#eventLog").innerHTML = ""; });
  el("#symbolSearch").addEventListener("input", (event) => renderSymbolDropdown(event.target.value));
  el("#symbolSearch").addEventListener("focus", (event) => renderSymbolDropdown(event.target.value));
  el("#symbol").addEventListener("change", (event) => addResearchSymbol(event.target.value));
  el("#strategyPreset").addEventListener("change", () => applyStrategyPreset(true));
  document.addEventListener("click", (event) => {
    const addButton = event.target.closest("[data-add-symbol]");
    if (addButton) {
      addResearchSymbol(addButton.dataset.addSymbol);
      el("#symbolSearch").value = "";
      renderSymbolDropdown("");
      el("#symbolDropdown").classList.remove("open");
      return;
    }
    const removeButton = event.target.closest("[data-remove-symbol]");
    if (removeButton) {
      removeResearchSymbol(removeButton.dataset.removeSymbol);
      return;
    }
    const primaryButton = event.target.closest("[data-primary-symbol]");
    if (primaryButton) {
      const symbol = primaryButton.dataset.primarySymbol;
      state.selectedResearchSymbols = [symbol, ...state.selectedResearchSymbols.filter((item) => item !== symbol)];
      renderSelectedSymbols();
      syncPrimaryResearchSymbol(symbol, true);
      return;
    }
    const replayPick = event.target.closest("[data-replay-symbol-pick]");
    if (replayPick) {
      addReplaySymbol(replayPick.dataset.replaySymbolPick);
      return;
    }
    const replayRemove = event.target.closest("[data-replay-symbol-remove]");
    if (replayRemove) {
      removeReplaySymbol(replayRemove.dataset.replaySymbolRemove);
      return;
    }
    const replayPrimary = event.target.closest("[data-replay-primary]");
    if (replayPrimary) {
      const symbol = replayPrimary.dataset.replayPrimary;
      state.replaySelectedSymbols = [symbol, ...state.replaySelectedSymbols.filter((item) => item !== symbol)];
      renderReplaySelectedSymbols();
      return;
    }
    if (!event.target.closest(".symbol-search-wrap")) {
      el("#symbolDropdown").classList.remove("open");
      el("#replaySymbolDropdown")?.classList.remove("open");
    }
    const dossierRow = event.target.closest("[data-dossier-symbol]");
    if (dossierRow) {
      if (event.target.closest("a")) return;
      const symbol = dossierRow.dataset.dossierSymbol;
      if (el("#dossierSymbol")) {
        el("#dossierSymbol").value = symbolDisplayName(symbol);
        el("#dossierSymbol").dataset.touched = "1";
      }
      runDossier(symbol);
    }
  });
  bindAgentConsole();
  setupButtonHelp();
  eventsBound = true;
}

function isKoreaMarketPriorityWindow(now = new Date()) {
  const day = now.getDay();
  const minutes = now.getHours() * 60 + now.getMinutes();
  return day >= 1 && day <= 5 && minutes >= 7 * 60 + 30 && minutes < 15 * 60 + 40;
}

let deferredResearchBootStarted = false;

async function runDeferredResearchBoot() {
  if (deferredResearchBootStarted || isKoreaMarketPriorityWindow()) return false;
  deferredResearchBootStarted = true;
  const jobs = [
    ["친구 배포 준비도", () => loadFriendReleaseReadiness()],
    ["완성도 점수", () => loadCodexstockMaturity(true)],
    ["백테스트", () => runBacktest()],
    ["다중 비교", () => runMultiBacktest()],
    ["검증 스위트", () => runValidationSuite()],
    ["승급 후보", () => loadPromotionCandidates()],
    ["Paper 리허설", () => loadPromotionRehearsals()],
    ["리허설 기억", () => loadPromotionRehearsalMemory()],
    ["강건성 검증", () => runRobustness()],
    ["보호 규칙", () => runProtections()],
    ["심층 연구", () => runLiveResearch()],
    ["경쟁력 감사", () => loadCompetitiveAudit(false)],
    ["자본 챌린지", () => loadCapitalChallenge(false)],
    ["AI 왕중왕전", () => loadAiTournament(false, true)],
    ["과거장 기록", () => loadReplayHistory()],
  ];
  for (const [label, job] of jobs) {
    try {
      await job();
    } catch (error) {
      addLog("장후 " + label + " 지연 작업 실패: " + error.message);
    }
  }
  return true;
}

async function boot() {
  localize();
  syncDefaultDates();
  renderProgramIntro();
  seedQuotes();
  buildWatchRows("#watchRows");
  buildWatchRows("#watchRowsTrading");
  buildTicker();
  renderStrategyPresets();
  bindEvents();
  renderCapitalActionHistory();
  setTimeout(() => {
    loadTodayTradeQuickSummary(true).catch((error) => addLog(`오늘 매매 요약 조회 실패: ${error.message}`));
  }, 0);
  await loadWatchlist();
  syncKisWatchlist(true).catch(() => {});
  renderSelectedSymbols();
  renderReplaySelectedSymbols();
  bindEvents();
  updateClock();
  renderMarket();
  loadAgentDaemon().catch((error) => addLog(`AI 현재 작업 조회 실패: ${error.message}`));
  loadAiStaff().catch((error) => addLog(`AI 직원 상태 조회 실패: ${error.message}`));
  loadPreMarketBriefing(false).catch((error) => addLog(`장전 브리핑 조회 실패: ${error.message}`));
  loadOpsStatus();
  loadLivePerformance().catch((error) => addLog(`실전 매매 성과 조회 실패: ${error.message}`));
  loadBrokerExecutionJournal(true).catch((error) => addLog(`최근 한투 체결 매매일지 조회 실패: ${error.message}`));
  loadLiveReasonBackfills().catch((error) => addLog(`매매 근거 보강 조회 실패: ${error.message}`));
  loadLiveOrderBlackbox({ silent: true }).catch((error) => addLog(`실전 주문 블랙박스 조회 실패: ${error.message}`));
  loadTradeBlockerSnapshot(true).catch((error) => addLog(`매매 대기 원인 빠른 진단 실패: ${error.message}`));
  loadTodayTradeQuickSummary(true).catch((error) => addLog(`오늘 매매 요약 조회 실패: ${error.message}`));
  loadExternalKnowledge(true).catch((error) => addLog(`외부학습 조회 실패: ${error.message}`));
  loadExternalEngineDashboard(true).catch((error) => addLog(`외부 엔진 상태 조회 실패: ${error.message}`));
  loadLiveAccountChanges(true).catch((error) => addLog(`실계좌 변화 감지 실패: ${error.message}`));
  loadIntradayMinuteRadar(true).catch((error) => addLog(`분봉 레이더 조회 실패: ${error.message}`));
  loadKisRankRadar(true).catch((error) => addLog(`한투 거래대금 랭킹 조회 실패: ${error.message}`));
  loadKisFluctuationRadar(true).catch((error) => addLog(`한투 등락률 랭킹 조회 실패: ${error.message}`));
  loadKisVolumePowerRadar(true).catch((error) => addLog(`한투 체결강도 랭킹 조회 실패: ${error.message}`));
  loadKisQuoteBalanceRadar(true).catch((error) => addLog(`한투 호가잔량 랭킹 조회 실패: ${error.message}`));
  loadConditionScreener(true).catch((error) => addLog(`조건검색 조회 실패: ${error.message}`));
  loadConditionScreenerHistory(true).catch((error) => addLog(`조건검색 기록 조회 실패: ${error.message}`));
  loadLiveDecisionContext(true).catch((error) => addLog(`AI 통합 판단 조회 실패: ${error.message}`));
  await loadSystemResources();
  await tickMarket(true);
  tickMarket(false);
  await loadUniverse();
  await loadStatus();
  await loadIntegrations();
  await loadPortfolio();
  await loadOpsStatus();
  await loadLogic();
  await loadJournal();
  await loadTradeJournalSummary().catch((error) => addLog(`통합 매매일지 조회 실패: ${error.message}`));
  await loadDaytradeActionCards(false).catch((error) => addLog(`단타 실행판 조회 실패: ${error.message}`));
  await loadAgentBrain();
  await loadAiBrief();
  await loadPreMarketBriefing(false);
  await loadAutopilot();
  await loadHealthSnapshots();
  await loadTelegramPollerStatus();
  await loadMarketRegime();
  await loadMission();
  await loadMarketClock();
  await loadWorklog();
  await loadPipeline();
  await loadAlerts();
  await loadDispatchCenter();
  await loadOpsStatus();
  await loadPortfolioTargets();
  await loadRecommendations(false);
  loadOpportunities(false);
  loadSectorCommittee(false);
  await loadScreener(false);
  await loadRadar(false);
  await loadSectorNews(false);
  await loadAgentDaemon();
  await loadAiStaff();
  runDeferredResearchBoot().catch((error) => addLog(`장후 연구 시작 실패: ${error.message}`));
  await loadKrMarketAnalysis();
  setInterval(() => {
    updateClock();
    tickMarket();
  }, 15000);
  setInterval(loadSystemResources, 10000);
  setInterval(loadIntegrations, 30000);
  setInterval(loadLivePerformance, 30000);
  setInterval(loadLiveReasonBackfills, 60000);
  setInterval(() => loadLiveOrderBlackbox({ silent: true }), 60000);
  setInterval(() => loadTradeBlockerSnapshot(true), 30000);
  setInterval(() => loadTodayTradeQuickSummary(true), 30000);
  setInterval(() => loadExternalKnowledge(true), 120000);
  setInterval(() => loadExternalEngineDashboard(true), 5000);
  setInterval(() => { if (!isKoreaMarketPriorityWindow()) loadFriendReleaseReadiness(); }, 120000);
  setInterval(loadAutopilot, 30000);
  setInterval(loadHealthSnapshots, 30000);
  setInterval(loadTelegramPollerStatus, 15000);
  setInterval(loadMarketRegime, 60000);
  setInterval(() => { if (!isKoreaMarketPriorityWindow()) loadPromotionCandidates(); }, 30000);
  setInterval(() => { if (!isKoreaMarketPriorityWindow()) loadPromotionRehearsals(); }, 30000);
  setInterval(() => { if (!isKoreaMarketPriorityWindow()) loadPromotionRehearsalMemory(); }, 30000);
  setInterval(loadMission, 30000);
  setInterval(loadMarketClock, 30000);
  setInterval(loadWorklog, 30000);
  setInterval(loadTradeJournalSummary, 60000);
  setInterval(() => loadDaytradeActionCards(false), 300000);
  setInterval(loadPipeline, 60000);
  setInterval(loadAlerts, 60000);
  setInterval(loadDispatchCenter, 60000);
  setInterval(() => loadPreMarketBriefing(false), 600000);
  setInterval(loadOpsStatus, 30000);
  setInterval(loadPortfolioTargets, 300000);
  setInterval(() => syncKisWatchlist(true), 120000);
  setInterval(() => { if (!isKoreaMarketPriorityWindow()) loadCodexstockMaturity(true); }, 120000);
  setInterval(() => { if (!isKoreaMarketPriorityWindow()) loadCompetitiveAudit(false); }, 120000);
  setInterval(() => loadRecommendations(false), 120000);
  setInterval(() => loadOpportunities(false), 300000);
  setInterval(() => loadSectorCommittee(false), 300000);
  setInterval(() => loadScreener(false), 120000);
  setInterval(() => loadRadar(false), 120000);
  setInterval(() => loadSectorNews(false), 300000);
  setInterval(() => { if (!isKoreaMarketPriorityWindow()) loadCapitalChallenge(false); }, 300000);
  setInterval(() => { if (!isKoreaMarketPriorityWindow()) loadAiTournament(false, true); }, 300000);
  setInterval(loadAgentDaemon, 30000);
  setInterval(loadAiStaff, 30000);
  setInterval(updateSmallAccountCountdowns, 30000);
  setInterval(() => { if (!isKoreaMarketPriorityWindow()) loadReplayHistory(); }, 120000);
  setInterval(() => runDeferredResearchBoot().catch(() => {}), 300000);
}

boot();
