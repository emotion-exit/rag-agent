import type { Metadata } from 'next';
import ConversationArea from '@/components/coversation-area';

export const metadata: Metadata = {
  title: 'index'
};

export default function Home() {
  return (
    <>
      <ConversationArea />
    </>
  );
}
