import React, { useState, useEffect, useRef } from 'react';
import { 
  User, ShoppingCart, ShieldCheck, Terminal, Send, RefreshCw, 
  AlertCircle, Database, Sparkles, AlertTriangle
} from 'lucide-react';
import AgentCore3D from './components/AgentCore3D';

interface CustomerProfile {
  id: number;
  name: string;
  email: string;
  tier: string;
  signup_date: string;
  past_refund_count: number;
}

interface Order {
  id: string;
  item_name: string;
  category: string;
  price: number;
  order_date: string;
  delivery_date: string | null;
  status: string;
}

interface RefundClaim {
  id: number;
  order_id: string;
  customer_name: string;
  customer_tier: string;
  item_name: string;
  category: string;
  amount: number;
  status: string;
  reason: string;
  citation: string;
  created_at: string;
}

interface TraceEvent {
  node: string;
  tool_called: string;
  tool_input: string;
  tool_output: string;
  reasoning: string;
}

interface AdminLog {
  id: string;
  customer_name: string;
  customer_id: number;
  timestamp: string;
  trace: TraceEvent;
}

interface ChatMessage {
  sender: 'user' | 'agent';
  text: string;
  isStreaming?: boolean;
}

export default function App() {
  // Database connection check
  const [dbConnected, setDbConnected] = useState<boolean | null>(null);
  
  // Customers selection
  const [customers, setCustomers] = useState<CustomerProfile[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number>(1);
  const [currentCustomerDetails, setCurrentCustomerDetails] = useState<{
    profile: CustomerProfile;
    orders: Order[];
    refunds: any[];
  } | null>(null);
  
  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [userInput, setUserInput] = useState('');
  const [agentStatus, setAgentStatus] = useState<string | null>(null);
  const [isAgentThinking, setIsAgentThinking] = useState(false);
  
  // Admin state
  const [adminLogs, setAdminLogs] = useState<AdminLog[]>([]);
  const [claimsList, setClaimsList] = useState<RefundClaim[]>([]);
  const [activeAdminTab, setActiveAdminTab] = useState<'traces' | 'claims'>('traces');
  const [showAdminPanel, setShowAdminPanel] = useState<boolean>(false);
  
  // WebSockets references
  const chatSocketRef = useRef<WebSocket | null>(null);
  const adminSocketRef = useRef<WebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Fetch initial customers
  const fetchCustomers = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/customers');
      if (res.ok) {
        const data = await res.json();
        setCustomers(data);
        setDbConnected(true);
      } else {
        setDbConnected(false);
      }
    } catch (e) {
      console.error("Database connection check failed", e);
      setDbConnected(false);
    }
  };

  // Fetch single customer details
  const fetchCustomerDetails = async (id: number) => {
    try {
      const res = await fetch(`http://localhost:8000/api/customers/${id}`);
      if (res.ok) {
        const data = await res.json();
        setCurrentCustomerDetails(data);
      }
    } catch (e) {
      console.error("Failed to load customer details", e);
    }
  };

  // Fetch refund claims for the dashboard database view
  const fetchClaims = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/refunds');
      if (res.ok) {
        const data = await res.json();
        setClaimsList(data);
      }
    } catch (e) {
      console.error("Failed to load claims list", e);
    }
  };

  useEffect(() => {
    fetchCustomers();
    fetchClaims();
  }, []);

  // Update customer details when customer ID changes
  useEffect(() => {
    if (dbConnected) {
      fetchCustomerDetails(selectedCustomerId);
      setChatMessages([
        { sender: 'agent', text: `Hello! I am your AI refund helper. How can I assist you with your orders today?` }
      ]);
      // Reconnect chat socket for the new customer
      connectChatSocket(selectedCustomerId);
    }
  }, [selectedCustomerId, dbConnected]);

  // Connect to Admin WebSockets log feed
  useEffect(() => {
    if (dbConnected) {
      connectAdminSocket();
    }
    return () => {
      if (adminSocketRef.current) adminSocketRef.current.close();
    };
  }, [dbConnected]);

  // Scroll to bottoms of logs and chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, agentStatus]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [adminLogs]);

  // WebSocket connection for Customer Chat
  const connectChatSocket = (customerId: number) => {
    if (chatSocketRef.current) {
      chatSocketRef.current.close();
    }
    
    const socket = new WebSocket(`ws://localhost:8000/ws/chat/${customerId}`);
    
    socket.onopen = () => {
      console.log(`Chat WebSocket connected for customer ${customerId}`);
    };
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'status') {
        setAgentStatus(data.content);
        setIsAgentThinking(true);
      } else if (data.type === 'token') {
        setAgentStatus(null);
        setIsAgentThinking(true);
        // Append token to the streaming agent response
        setChatMessages(prev => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.sender === 'agent' && lastMsg.isStreaming) {
            return [
              ...prev.slice(0, -1),
              { sender: 'agent', text: lastMsg.text + data.content, isStreaming: true }
            ];
          } else {
            return [
              ...prev,
              { sender: 'agent', text: data.content, isStreaming: true }
            ];
          }
        });
      } else if (data.type === 'end_response') {
        setIsAgentThinking(false);
        setAgentStatus(null);
        // Remove streaming flag from last message
        setChatMessages(prev => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.sender === 'agent' && lastMsg.isStreaming) {
            return [
              ...prev.slice(0, -1),
              { sender: 'agent', text: lastMsg.text }
            ];
          }
          return prev;
        });
        // Refresh details & claims lists since transactions might have completed
        fetchCustomerDetails(selectedCustomerId);
        fetchClaims();
      } else if (data.type === 'error') {
        setIsAgentThinking(false);
        setAgentStatus(null);
        setChatMessages(prev => [
          ...prev,
          { sender: 'agent', text: `⚠️ Error: ${data.content}` }
        ]);
      }
    };
    
    socket.onclose = () => {
      console.log(`Chat WebSocket closed for customer ${customerId}`);
    };
    
    chatSocketRef.current = socket;
  };

  // WebSocket connection for Admin Logs
  const connectAdminSocket = () => {
    if (adminSocketRef.current) {
      adminSocketRef.current.close();
    }
    
    const socket = new WebSocket(`ws://localhost:8000/ws/admin/logs`);
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'trace') {
        const newLog: AdminLog = {
          id: Math.random().toString(36).substring(2, 9),
          customer_name: data.customer_name,
          customer_id: data.customer_id,
          timestamp: new Date().toLocaleTimeString(),
          trace: data.data
        };
        setAdminLogs(prev => [...prev, newLog]);
      }
    };
    
    socket.onclose = () => {
      console.log("Admin WebSocket closed. Reconnecting...");
      setTimeout(() => connectAdminSocket(), 3000);
    };
    
    adminSocketRef.current = socket;
  };

  const sendMessage = () => {
    if (!userInput.trim() || !chatSocketRef.current) return;
    
    // Send user message through websocket
    chatSocketRef.current.send(JSON.stringify({ text: userInput }));
    
    setChatMessages(prev => [...prev, { sender: 'user', text: userInput }]);
    setUserInput('');
    setIsAgentThinking(true);
    setAgentStatus("Routing message to intake agent...");
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  };

  // Quick prompt presets helper
  const sendQuickPrompt = (prompt: string) => {
    setUserInput(prompt);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col antialiased">
      {/* Top Header */}
      <header className="border-b border-slate-900 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50 py-3 px-6 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-500 flex items-center justify-center glow-purple">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-violet-400 to-indigo-300 bg-clip-text text-transparent">
              AutoRefund LangGraph Agent
            </h1>
            <p className="text-[10px] text-slate-400 font-semibold tracking-wider uppercase">
              Agentic RAG State Machine + Real-Time Streaming Logs
            </p>
          </div>
        </div>
        
        {/* Status Indicator */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-slate-400 font-medium">Database:</span>
            {dbConnected === null && (
              <span className="flex items-center text-yellow-400 font-medium">
                <RefreshCw className="h-3 w-3 animate-spin mr-1" /> Checking...
              </span>
            )}
            {dbConnected === true && (
              <span className="flex items-center text-emerald-400 font-medium bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-900">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse mr-1.5"></span> Connected
              </span>
            )}
            {dbConnected === false && (
              <span className="flex items-center text-rose-400 font-medium bg-rose-950/50 px-2 py-0.5 rounded border border-rose-900">
                <AlertCircle className="h-3 w-3 mr-1" /> Disconnected
              </span>
            )}
          </div>
          
          {/* Admin panel toggle button */}
          <button 
            onClick={() => setShowAdminPanel(prev => !prev)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition duration-200 border ${
              showAdminPanel 
                ? 'bg-purple-900/40 text-purple-400 border-purple-800/40 hover:bg-purple-900/60' 
                : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200 hover:bg-slate-850'
            }`}
            title="Toggle Admin reasoning logs and transaction claims list panel"
          >
            <Terminal className="h-3.5 w-3.5" />
            <span>{showAdminPanel ? 'Admin View: ON' : 'Admin View: OFF'}</span>
          </button>

          <button 
            onClick={fetchCustomers}
            className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-white transition duration-200"
            title="Reconnect Database"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* Warning if DB disconnected */}
      {dbConnected === false && (
        <div className="bg-rose-950/40 border-b border-rose-900/50 text-rose-200 px-6 py-3 text-xs flex items-center space-x-3">
          <AlertTriangle className="h-5 w-5 text-rose-400 flex-shrink-0" />
          <div className="flex-1">
            <p className="font-semibold">PostgreSQL Database Connection Failed</p>
            <p className="opacity-80">
              Please check if the Docker container is running by opening <strong>Docker Desktop</strong> and ensuring you start the services using <code className="bg-black/50 px-1 py-0.5 rounded text-white">docker-compose up -d</code>. If it failed to pull, running the script with the database running will populate all customers.
            </p>
          </div>
        </div>
      )}

      {/* Main Split Layout */}
      <main className="flex-1 flex flex-col lg:flex-row overflow-hidden h-[calc(100vh-65px)]">

        {/* ================= LEFT SIDE: CUSTOMER HUB ================= */}
        <section className={`w-full ${showAdminPanel ? 'lg:w-1/2' : 'lg:w-[35%]'} border-r border-slate-900 flex flex-col bg-slate-950 overflow-y-auto`}>
          {/* Customer Selection Toolbar */}
          <div className="p-4 border-b border-slate-900 bg-slate-950 flex flex-col space-y-3">
            <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
              Select Customer Profile to Simulate
            </label>
            <div className="flex space-x-2">
              <select
                value={selectedCustomerId}
                onChange={(e) => setSelectedCustomerId(Number(e.target.value))}
                disabled={!dbConnected}
                className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-purple-500 focus:outline-none"
              >
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    Customer #{c.id}: {c.name} ({c.tier.toUpperCase()} • Refunds: {c.past_refund_count})
                  </option>
                ))}
              </select>
            </div>
            
            {/* Quick Presets based on policy cases */}
            <div className="flex flex-col space-y-1.5 mt-1">
              <span className="text-[9px] text-slate-400 font-semibold uppercase">Quick Query Presets</span>
              <div className="flex flex-wrap gap-1">
                <button 
                  onClick={() => sendQuickPrompt("Hi, I bought Premium Headphones (ORD-001) but the right channel broke. I want a refund please.")}
                  className="bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] py-1 px-2.5 rounded-full text-slate-300 transition duration-150"
                >
                  ORD-001 (Refund Window 8d)
                </button>
                <button 
                  onClick={() => sendQuickPrompt("I purchased a Winter Jacket (ORD-003) but it is too big. I want to return it for a refund.")}
                  className="bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] py-1 px-2.5 rounded-full text-slate-300 transition duration-150"
                >
                  ORD-003 (Apparel 27d)
                </button>
                <button 
                  onClick={() => sendQuickPrompt("I want a refund for my e-book ORD-011. It's not what I expected.")}
                  className="bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] py-1 px-2.5 rounded-full text-slate-300 transition duration-150"
                >
                  ORD-011 (Digital goods)
                </button>
                <button 
                  onClick={() => sendQuickPrompt("Please refund my Gaming Console ORD-017. It's defective.")}
                  className="bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] py-1 px-2.5 rounded-full text-slate-300 transition duration-150"
                >
                  ORD-017 (Exceeds $200 Cap)
                </button>
              </div>
            </div>
          </div>

          {/* Customer Profile & Order History Sheet */}
          {currentCustomerDetails && (
            <div className="p-4 bg-slate-900/30 border-b border-slate-900 flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <User className="h-4 w-4 text-purple-400" />
                  <span className="text-xs font-bold text-slate-200">Customer Details</span>
                </div>
                <span className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded ${
                  currentCustomerDetails.profile.tier === 'premium' 
                    ? 'bg-amber-950/60 text-amber-400 border border-amber-800' 
                    : 'bg-slate-800 text-slate-400'
                }`}>
                  {currentCustomerDetails.profile.tier} tier
                </span>
              </div>
              
              {/* Profile Card */}
              <div className="grid grid-cols-3 gap-2 text-[11px] bg-slate-900/50 p-2.5 rounded-lg border border-slate-900">
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase font-bold">Email</span>
                  <span className="text-slate-300 truncate font-medium">{currentCustomerDetails.profile.email}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase font-bold">Signup Date</span>
                  <span className="text-slate-300 font-medium">{currentCustomerDetails.profile.signup_date}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase font-bold">Approved Refunds</span>
                  <span className={`font-bold ${currentCustomerDetails.profile.past_refund_count >= 3 ? 'text-rose-400' : 'text-emerald-400'}`}>
                    {currentCustomerDetails.profile.past_refund_count}
                  </span>
                </div>
              </div>

              {/* Order List */}
              <div className="flex flex-col space-y-1.5 pb-2">
                <div className="flex items-center space-x-1">
                  <ShoppingCart className="h-3.5 w-3.5 text-blue-400" />
                  <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wide">Active Order History</span>
                </div>
                <div className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1">
                  {currentCustomerDetails.orders.map((o) => (
                    <div key={o.id} className="flex justify-between items-center text-[10px] bg-slate-900/40 p-2 rounded border border-slate-900 hover:border-slate-800 transition">
                      <div className="flex flex-col">
                        <span className="text-slate-200 font-medium">{o.item_name}</span>
                        <div className="flex space-x-2 text-slate-500">
                          <span>ID: <strong className="text-slate-400 font-normal">{o.id}</strong></span>
                          <span>•</span>
                          <span>Delivered: <strong className="text-slate-400 font-normal">{o.delivery_date || 'N/A'}</strong></span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end">
                        <span className="text-slate-300 font-bold">${o.price.toFixed(2)}</span>
                        <span className="text-[9px] text-slate-500 font-semibold uppercase">{o.category}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* If admin panel is open, we display the Chat panel on the left under the customer workspace to allow chat */}
          {showAdminPanel ? (
            <div className="flex-1 flex flex-col min-h-[350px] bg-slate-950">
              {/* Chat Messenger Panel (compact view) */}
              <div className="p-3 border-b border-slate-900 bg-slate-950 flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wide">Customer Chat Sim</span>
                <span className="text-[9px] text-slate-500">WebSocket Session</span>
              </div>
              <div className="flex-1 overflow-y-auto p-3 space-y-2.5 flex flex-col max-h-[300px]">
                {chatMessages.map((msg, index) => (
                  <div 
                    key={index} 
                    className={`flex flex-col max-w-[85%] ${
                      msg.sender === 'user' ? 'self-end items-end' : 'self-start items-start'
                    }`}
                  >
                    <div className={`px-3 py-2 rounded-xl text-[11px] leading-relaxed ${
                      msg.sender === 'user' 
                        ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-br-none shadow-lg' 
                        : 'bg-slate-900 border border-slate-850 text-slate-200 rounded-bl-none'
                    }`}>
                      {msg.text}
                    </div>
                  </div>
                ))}
                {isAgentThinking && agentStatus && (
                  <div className="self-start flex items-center space-x-1.5 text-[9px] text-purple-400 bg-purple-950/20 border border-purple-900/30 px-2.5 py-1 rounded-full animate-pulse">
                    <RefreshCw className="h-2.5 w-2.5 animate-spin" />
                    <span>{agentStatus}</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
              <div className="p-2 border-t border-slate-900 bg-slate-950 flex space-x-2">
                <input
                  type="text"
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  onKeyDown={handleKeyPress}
                  placeholder="Ask for refund..."
                  disabled={isAgentThinking || !dbConnected}
                  className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-[11px] focus:outline-none focus:ring-1 focus:ring-purple-500 disabled:opacity-50"
                />
                <button
                  onClick={sendMessage}
                  disabled={isAgentThinking || !userInput.trim() || !dbConnected}
                  className="bg-purple-600 hover:bg-purple-500 text-white px-3.5 rounded-lg text-xs"
                >
                  Send
                </button>
              </div>
            </div>
          ) : (
            <div className="p-4 flex-1 flex flex-col min-h-[260px] bg-slate-950">
              {/* Otherwise, display the interactive 3D visualizer orb */}
              <AgentCore3D />
            </div>
          )}
        </section>

        {/* ================= RIGHT SIDE SECTION ================= */}
        {showAdminPanel ? (
          <section className="w-full lg:w-1/2 flex flex-col bg-slate-950 overflow-hidden">
            {/* ================= RIGHT SIDE: ADMIN VIEW ================= */}
            {/* Admin Panels Menu Tabs */}
            <div className="border-b border-slate-900 bg-slate-950/90 flex justify-between items-center px-4 py-2">
              <div className="flex space-x-2">
                <button
                  onClick={() => setActiveAdminTab('traces')}
                  className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-bold transition duration-200 ${
                    activeAdminTab === 'traces' 
                      ? 'bg-purple-900/40 text-purple-400 border border-purple-800/40' 
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Terminal className="h-3.5 w-3.5" />
                  <span>Live Reasoning Traces</span>
                </button>
                
                <button
                  onClick={() => setActiveAdminTab('claims')}
                  className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-bold transition duration-200 ${
                    activeAdminTab === 'claims' 
                      ? 'bg-purple-900/40 text-purple-400 border border-purple-800/40' 
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Database className="h-3.5 w-3.5" />
                  <span>Refund Claims Log</span>
                </button>
              </div>
              
              <button 
                onClick={fetchClaims}
                className="p-1 hover:bg-slate-900 rounded text-slate-400 hover:text-slate-200"
                title="Refresh database records"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Live Traces Tab view */}
            {activeAdminTab === 'traces' ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                
                {/* 3D Core Visualizer & System Architecture Summary */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 border-b border-slate-900 bg-slate-900/10">
                  {/* 3D Agent Core Graphic */}
                  <div className="h-full">
                    <AgentCore3D />
                  </div>
                  
                  {/* Visual Architecture Mini-card */}
                  <div className="bg-slate-900/40 border border-slate-900 rounded-2xl p-4 flex flex-col justify-between text-xs">
                    <div className="space-y-1.5">
                      <div className="flex items-center space-x-1.5 text-purple-400 font-bold uppercase tracking-wider text-[10px]">
                        <ShieldCheck className="h-4 w-4" />
                        <span>Security & Policy Engine</span>
                      </div>
                      <p className="text-slate-400 text-[11px] leading-relaxed">
                        LangGraph orchestrates the refund evaluation. First, it extracts identifiers, fetches full profile history, embeds context to search rules in <span className="text-slate-200 font-semibold">pgvector</span>, and checks customer frequencies and caps prior to deciding.
                      </p>
                    </div>
                    
                    {/* System limits table */}
                    <div className="mt-3 border-t border-slate-900 pt-2 space-y-1 text-[10px] text-slate-500 font-medium">
                      <div className="flex justify-between">
                        <span>Annual Refund Limit:</span>
                        <span className="text-slate-300 font-semibold">$200.00</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Standard Restocking Fee:</span>
                        <span className="text-slate-300 font-semibold">10%</span>
                      </div>
                      <div className="flex justify-between font-bold text-rose-500">
                        <span>Abuse Escalation Trigger:</span>
                        <span>&ge; 3 Refunds</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Scrolling Console Logs Terminal */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-black/40 font-mono">
                  {adminLogs.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-600">
                      <Terminal className="h-10 w-10 mb-2 opacity-50" />
                      <p className="text-xs">Console is listening. Ask the customer bot a refund question on the left to trigger the LangGraph execution flow.</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="text-[10px] text-purple-400 font-bold border-b border-purple-900/30 pb-1 flex items-center">
                        <span className="h-1.5 w-1.5 rounded-full bg-purple-400 animate-ping mr-2"></span>
                        LIVE STATE MACHINE EXECUTION TRACES
                      </div>
                      {adminLogs.map((log) => (
                        <div key={log.id} className="bg-slate-950 border border-slate-900 rounded-lg overflow-hidden text-[11px]">
                          {/* Header */}
                          <div className="bg-slate-900/60 px-3 py-1.5 flex justify-between items-center text-[10px] text-slate-400 border-b border-slate-900">
                            <span className="font-bold flex items-center">
                              <span className="h-2 w-2 rounded bg-purple-600 inline-block mr-1.5"></span>
                              NODE: {log.trace.node.toUpperCase()}
                            </span>
                            <span>Session: {log.customer_name} (#{log.customer_id}) • {log.timestamp}</span>
                          </div>
                          
                          {/* Log fields */}
                          <div className="p-2.5 space-y-1.5">
                            {log.trace.tool_called !== "None" && (
                              <div>
                                <span className="text-blue-400 font-semibold">Tool Invoke:</span>{' '}
                                <code className="text-blue-300 bg-blue-950/30 px-1 py-0.5 rounded text-[10px]">
                                  {log.trace.tool_called}({log.trace.tool_input})
                                </code>
                              </div>
                            )}
                            <div>
                              <span className="text-emerald-400 font-semibold">Tool Return:</span>{' '}
                              <span className="text-slate-300">{log.trace.tool_output}</span>
                            </div>
                            <div className="border-t border-slate-900/50 pt-1.5 mt-1.5">
                              <span className="text-indigo-400 font-semibold">Agent Reasoning:</span>{' '}
                              <span className="text-slate-400 italic">{log.trace.reasoning}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                      <div ref={logsEndRef} />
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {/* Claims Tab view */}
                <div className="flex items-center space-x-1.5 pb-2 border-b border-slate-900">
                  <Database className="h-4 w-4 text-purple-400" />
                  <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">Historical Postgres Transactions</span>
                </div>
                
                {claimsList.length === 0 ? (
                  <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-xs">
                    <Database className="h-8 w-8 mb-2 opacity-55" />
                    <span>No claims recorded in database yet.</span>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {claimsList.map((claim) => (
                      <div key={claim.id} className="bg-slate-900/40 border border-slate-900 p-3 rounded-xl flex flex-col space-y-2 text-xs">
                        
                        {/* Top claim line */}
                        <div className="flex justify-between items-start">
                          <div className="flex flex-col">
                            <span className="font-bold text-slate-200">{claim.customer_name} ({claim.customer_tier.toUpperCase()})</span>
                            <span className="text-[10px] text-slate-500">Order: <strong className="text-slate-400 font-normal">{claim.order_id}</strong> ({claim.item_name})</span>
                          </div>
                          <div className="flex flex-col items-end">
                            <span className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded border ${
                              claim.status === 'approved' 
                                ? 'bg-emerald-950/50 text-emerald-400 border-emerald-900'
                                : claim.status === 'denied'
                                ? 'bg-rose-950/50 text-rose-400 border-rose-900'
                                : 'bg-amber-950/50 text-amber-400 border-amber-900'
                            }`}>
                              {claim.status}
                            </span>
                            <span className="text-[10px] text-slate-400 font-bold mt-1">
                              {claim.amount > 0 ? `$${claim.amount.toFixed(2)}` : '-'}
                            </span>
                          </div>
                        </div>
                        
                        {/* Decider rationale */}
                        <div className="bg-slate-950/60 p-2 rounded text-[11px] border border-slate-900 text-slate-400 space-y-1">
                          <p><strong className="text-slate-300 font-medium">Policy Rationale:</strong> {claim.reason}</p>
                          {claim.citation && (
                            <p className="text-[10px] text-purple-400 italic">
                              <strong className="text-purple-300 not-italic font-medium">Source:</strong> &ldquo;{claim.citation}&rdquo;
                            </p>
                          )}
                        </div>
                        
                        <div className="text-[9px] text-slate-600 flex justify-between">
                          <span>Transaction Timestamp: {claim.created_at}</span>
                          <span>Claim #{claim.id}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>
        ) : (
          <section className="w-full lg:w-[65%] flex flex-col bg-slate-950 overflow-hidden">
            {/* ================= RIGHT SIDE: CHAT MESSENGER (Default Clean Chat Panel) ================= */}
            {/* Chat Messenger Header */}
            <div className="p-4 border-b border-slate-900 bg-slate-950 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">AI Refund Agent Assistant</span>
              </div>
              <div className="text-[10px] text-slate-500 font-mono">Status: Active (Local Policy Mode)</div>
            </div>

            {/* Scrollable messages container */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 flex flex-col">
              {chatMessages.map((msg, index) => (
                <div 
                  key={index} 
                  className={`flex flex-col max-w-[85%] ${
                    msg.sender === 'user' ? 'self-end items-end' : 'self-start items-start'
                  }`}
                >
                  <div className={`px-3.5 py-2.5 rounded-2xl text-xs leading-relaxed ${
                    msg.sender === 'user' 
                      ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-br-none shadow-lg shadow-violet-950/30' 
                      : 'bg-slate-900 border border-slate-850 text-slate-200 rounded-bl-none'
                  }`}>
                    {msg.text}
                    {msg.isStreaming && (
                      <span className="inline-block w-1.5 h-3 ml-1 bg-purple-400 animate-pulse align-middle"></span>
                    )}
                  </div>
                </div>
              ))}
              
              {/* Agent Thinking States */}
              {isAgentThinking && agentStatus && (
                <div className="self-start flex items-center space-x-2 text-[10px] text-purple-400 font-medium bg-purple-950/20 border border-purple-900/30 px-3 py-1.5 rounded-full animate-pulse">
                  <RefreshCw className="h-3 w-3 animate-spin" />
                  <span>{agentStatus}</span>
                </div>
              )}
              
              <div ref={chatEndRef} />
            </div>

            {/* Chat Input Field */}
            <div className="p-3 border-t border-slate-900 bg-slate-950/50 flex space-x-2">
              <input
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="Ask about a refund (e.g. 'I want a refund for ORD-001')"
                disabled={isAgentThinking || !dbConnected}
                className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-xs focus:ring-1 focus:ring-purple-500 focus:outline-none disabled:opacity-50"
              />
              <button
                onClick={sendMessage}
                disabled={isAgentThinking || !userInput.trim() || !dbConnected}
                className="bg-purple-600 hover:bg-purple-500 disabled:bg-slate-800 text-white p-3 rounded-xl transition shadow-lg shadow-purple-950/20 disabled:shadow-none flex items-center justify-center"
              >
                <Send className="h-4.5 w-4.5" />
              </button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
