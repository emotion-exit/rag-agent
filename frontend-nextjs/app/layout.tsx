import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: {
    template: '%s - RAG Agent',
    default: 'RAG Agent'
  },
  description: 'create by next'
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html className='h-full antialiased'>
      <body className='h-screen w-screen overflow-y-hidden px-[25%] py-20 flex flex-col items-center'>
        {children}
      </body>
    </html>
  );
}
