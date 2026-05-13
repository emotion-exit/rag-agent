'use client';
import { Streamdown } from 'streamdown';
import 'streamdown/styles.css';
import { createCodePlugin } from '@streamdown/code';
import { useState, useRef, useEffect } from 'react';
type Message = {
  role: 'user' | 'assistant';
  content: string;
};
const code = createCodePlugin({
  themes: ['github-light', 'github-dark'] // [light, dark]
});
export default function ConversationArea() {
  const [messages, setMessages] = useState<Message[]>([]);

  // 调用后端接口发送消息
  async function sendMessage(userPrompt: string) {
    if (userPrompt.trim() === '') return;
    setMessages((prevMessages) => [
      ...prevMessages,
      {
        role: 'user',
        content: userPrompt
      }
    ]);
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ message: userPrompt })
    });
    if (response.ok) {
      const reader = response.body?.getReader();
      if (reader) {
        const decoder = new TextDecoder('utf-8');
        const assistantMessage: Message = {
          role: 'assistant',
          content: ''
        };
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          const lines = chunk.split('\n').filter((line) => line.trim() !== '');
          for (const line of lines) {
            try {
              const parsed = JSON.parse(line);
              if (parsed.type === 'token') {
                assistantMessage.content += parsed.text.kwargs.content!;
                setMessages((prevMessages) => {
                  const lastMessage = prevMessages[prevMessages.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    return [...prevMessages.slice(0, -1), assistantMessage];
                  } else {
                    return [...prevMessages, assistantMessage];
                  }
                });
              } else if (parsed.type === 'done') {
                // 处理完成
              } else if (parsed.type === 'error') {
                // 处理错误
                console.error('Error from server:', JSON.stringify(parsed));
              }
            } catch (error) {
              console.error('Failed to parse chunk:', chunk, error);
            }
          }
        }
      }
    } else {
      console.error('Request failed:', response.status, response.statusText);
    }
  }

  const listRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight
    });
  }, [messages]);

  return (
    <div className='w-200 bg-background text-foreground shadow-xl rounded h-full flex flex-col p-1'>
      <ChatArea messages={messages} listRef={listRef} />
      <SendArea sendMessage={sendMessage} />
    </div>
  );
}

function ChatArea({
  messages,
  listRef
}: {
  messages: Message[];
  listRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <div
      ref={listRef}
      className='list flex-1 overflow-y-auto  flex flex-col gap-4 p-3'>
      {messages.map((message, index) => (
        <div
          key={index}
          className={`px-4 py-2 rounded ${
            message.role === 'user'
              ? 'max-w-[70%]  bg-gray-600 text-gray-200 self-end'
              : 'w-[70%] bg-gray-200 text-gray-600 self-start'
          }`}>
          <Streamdown
            key={index}
            plugins={{ code }}
            isAnimating={status === 'streaming'}>
            {message.content}
          </Streamdown>
        </div>
      ))}
    </div>
  );
}

function SendArea({ sendMessage }: { sendMessage: (message: string) => void }) {
  return (
    <div className='w-full h-16 rounded flex items-center px-4'>
      <input
        type='text'
        placeholder='请输入消息...'
        className='flex-1 h-10 rounded px-4 mr-4 border border-gray-600 outline-none'
        onKeyDown={(e) => {
          const nativeEvent = e.nativeEvent as KeyboardEvent;
          if (nativeEvent.isComposing) {
            return;
          }
          if (e.key === 'Enter') {
            const target = e.target as HTMLInputElement;
            sendMessage(target.value);
            target.value = '';
          }
        }}
      />
      <button
        className='bg-foreground text-background px-4 py-2 rounded outline-none'
        onClick={() => {
          const input = document.querySelector(
            'input[type="text"]'
          ) as HTMLInputElement | null;
          if (input) {
            sendMessage(input.value);
            input.value = '';
          }
        }}>
        发送
      </button>
    </div>
  );
}
