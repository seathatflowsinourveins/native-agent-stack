import type { Metadata } from 'next';
import './style.css';

export const metadata: Metadata = {
  title: 'Run ledger',
  description: 'Track local engineering runs and their recorded status changes.',
};
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
