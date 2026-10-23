import React, { useEffect, useRef, useState } from 'react';
import { Maximize2, MessageCircle, Minimize2, Send, X } from 'lucide-react';
import { getApiBaseUrl } from '../../lib/api';
import Button from '../ui/Button';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const ChatBot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const toggleChat = () => {
    setIsOpen((previous) => !previous);
    if (!isOpen) {
      setIsMinimized(false);
    }
  };

  const handleSendMessage = async () => {
    if (!message.trim()) {
      return;
    }

    const userMessage: Message = { role: 'user', content: message.trim() };
    setMessages((previous) => [...previous, userMessage]);
    setMessage('');
    setIsLoading(true);

    try {
      const response = await fetch(`${getApiBaseUrl()}/chatbot/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage.content,
          history: messages,
        }),
      });

      const data = await response.json();
      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          content:
            data.success === false
              ? data.response || 'Cardios Assistant could not answer that request.'
              : data.response,
        },
      ]);
    } catch (chatError) {
      console.error('Error sending message:', chatError);
      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          content:
            'Network error. Cardios Assistant could not reach the backend service. Make sure the Flask server is running.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSendMessage();
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="fixed bottom-5 right-5 z-50">
      <button
        onClick={toggleChat}
        className="flex items-center justify-center rounded-full bg-emerald-500 p-3 text-white shadow-[0_18px_35px_rgba(16,185,129,0.28)] transition hover:-translate-y-0.5 hover:bg-emerald-600"
        aria-label="Open Cardios assistant"
      >
        <MessageCircle size={24} />
      </button>

      {isOpen ? (
        <div
          className={`absolute bottom-16 right-0 overflow-hidden rounded-[28px] border border-emerald-100 bg-white shadow-[0_30px_70px_rgba(14,50,37,0.18)] transition-all duration-300 ${
            isMinimized ? 'h-16 w-80 md:w-96' : 'h-[520px] w-80 md:w-96'
          }`}
        >
          <div className="flex items-center justify-between bg-gradient-to-r from-[#0c5a3e] to-[#13a868] px-4 py-4 text-white">
            <div>
              <h3 className="font-sora text-lg font-semibold">Cardios Assistant</h3>
              <p className="text-xs uppercase tracking-[0.18em] text-emerald-100/80">
                Cardiac AI guide
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsMinimized((previous) => !previous)}
                className="rounded-full p-2 transition hover:bg-white/10"
              >
                {isMinimized ? <Maximize2 size={16} /> : <Minimize2 size={16} />}
              </button>
              <button onClick={toggleChat} className="rounded-full p-2 transition hover:bg-white/10">
                <X size={16} />
              </button>
            </div>
          </div>

          {!isMinimized ? (
            <>
              <div className="h-[390px] overflow-y-auto bg-[#f6fbf8] p-4">
                {messages.length === 0 ? (
                  <div className="rounded-[24px] bg-white p-4 text-sm leading-7 text-slate-600 shadow-sm">
                    <p className="font-medium text-slate-900">Ask Cardios anything.</p>
                    <p className="mt-2">
                      Try questions about heart-risk factors, ECG interpretation context, or how to use
                      the assessment and monitoring workflow.
                    </p>
                  </div>
                ) : (
                  messages.map((entry, index) => (
                    <div
                      key={`${entry.role}-${index}`}
                      className={`mb-3 ${entry.role === 'user' ? 'text-right' : 'text-left'}`}
                    >
                      <div
                        className={`inline-block max-w-[85%] rounded-[22px] px-4 py-3 text-sm leading-7 ${
                          entry.role === 'user'
                            ? 'bg-emerald-500 text-white'
                            : 'bg-white text-slate-700 shadow-sm'
                        }`}
                      >
                        {entry.content}
                      </div>
                    </div>
                  ))
                )}

                {isLoading ? (
                  <div className="text-left">
                    <div className="inline-flex rounded-[22px] bg-white px-4 py-3 shadow-sm">
                      <div className="flex gap-2">
                        <span className="h-2 w-2 animate-bounce rounded-full bg-emerald-400" />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-emerald-400 [animation-delay:120ms]" />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-emerald-400 [animation-delay:240ms]" />
                      </div>
                    </div>
                  </div>
                ) : null}
                <div ref={messagesEndRef} />
              </div>

              <div className="border-t border-emerald-100 bg-white p-3">
                <div className="flex items-end gap-2">
                  <textarea
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                    onKeyDown={handleKeyPress}
                    placeholder="Ask about risk factors, ECG, or using Cardios..."
                    className="min-h-[52px] flex-1 resize-none rounded-[20px] border border-emerald-100 px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-emerald-300 focus:ring-2 focus:ring-emerald-100"
                    rows={1}
                    disabled={isLoading}
                  />
                  <Button
                    onClick={handleSendMessage}
                    disabled={isLoading || !message.trim()}
                    className="h-[52px] w-[52px] rounded-[18px] px-0"
                  >
                    <Send size={18} />
                  </Button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

export default ChatBot;
