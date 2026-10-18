import Link from "next/link";
import { PublicityEarnings } from "../../components/publicity-earnings";

export default function PublicityEarningsPage() {
  return <main className="mx-auto min-h-screen max-w-7xl p-4 text-ink md:p-8">
    <Link href="/" className="mb-5 inline-block text-sm font-bold underline">Back to dashboard</Link>
    <PublicityEarnings />
  </main>;
}
