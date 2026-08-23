import React, { useState, useRef, useEffect } from 'react';

export interface ChatMessage {
  id: string;
  type: 'user' | 'bot';
  content: string;
  timestamp: Date;
}

interface ChatBubbleProps {
  messages?: ChatMessage[];
  onSendMessage?: (message: string) => void;
  title?: string;
}

const ChatBubble: React.FC<ChatBubbleProps> = ({
  messages = [
    {
      id: '1',
      type: 'bot',
      content: 'Hi! I can help you optimize scheduling, answer questions about your data, or guide you through setup. What can I do?',
      timestamp: new Date(),
    },
  ],
  onSendMessage,
  title = 'Ask Claude',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSend = () => {
    if (inputValue.trim() && onSendMessage) {
      onSendMessage(inputValue);
      setInputValue('');
    }
  };

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: 'fixed',
          bottom: '32px',
          right: '32px',
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          background: 'var(--accent)',
          color: 'white',
          border: 'none',
          cursor: 'pointer',
          fontSize: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 8px 24px rgba(0, 217, 255, 0.3)',
          transition: 'all 0.2s',
          zIndex: 100,
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.transform = 'scale(1.1)';
          (e.currentTarget as HTMLElement).style.boxShadow = '0 12px 32px rgba(0, 217, 255, 0.4)';
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.transform = 'scale(1)';
          (e.currentTarget as HTMLElement).style.boxShadow = '0 8px 24px rgba(0, 217, 255, 0.3)';
        }}
      >
        💬
      </button>

      {/* Chat Popup */}
      {isOpen && (
        <div
          style={{
            position: 'fixed',
            bottom: '104px',
            right: '32px',
            width: '360px',
            maxHeight: '600px',
            background: 'var(--surface)',
            borderRadius: '12px',
            boxShadow: '0 16px 48px rgba(0, 0, 0, 0.12)',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 100,
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '16px 20px',
              borderBottom: '1px solid #f0f0f0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span style={{ fontWeight: 600, fontSize: '14px' }}>{title}</span>
            <button
              onClick={() => setIsOpen(false)}
              style={{
                background: 'none',
                border: 'none',
                fontSize: '20px',
                cursor: 'pointer',
                color: 'var(--text-muted)',
                padding: '0',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              padding: '20px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            {messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  fontSize: '13px',
                  lineHeight: 1.5,
                  padding: '12px',
                  borderRadius: '8px',
                  maxWidth: '280px',
                  wordWrap: 'break-word',
                  ...( msg.type === 'bot'
                    ? {
                        background: '#f0f0f0',
                        color: 'var(--text)',
                        alignSelf: 'flex-start',
                      }
                    : {
                        background: 'var(--accent)',
                        color: 'white',
                        alignSelf: 'flex-end',
                      }
                  ),
                }}
              >
                {msg.content}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div
            style={{
              padding: '16px 20px',
              borderTop: '1px solid #f0f0f0',
              display: 'flex',
              gap: '8px',
            }}
          >
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') handleSend();
              }}
              placeholder="Ask anything..."
              style={{
                flex: 1,
                border: '1px solid #e0e0e0',
                borderRadius: '6px',
                padding: '8px 12px',
                fontSize: '13px',
                fontFamily: 'inherit',
                color: 'var(--text)',
                background: 'var(--surface)',
              }}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim()}
              style={{
                background: 'var(--accent)',
                border: 'none',
                color: 'white',
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                cursor: inputValue.trim() ? 'pointer' : 'not-allowed',
                fontSize: '16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: inputValue.trim() ? 1 : 0.5,
              }}
            >
              ↑
            </button>
          </div>
        </div>
      )}
    </>
  );
};

export default ChatBubble;
