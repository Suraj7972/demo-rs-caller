import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle>PropCall</CardTitle>
          <CardDescription>
            Dashboard scaffold. Campaigns, leads, calls and analytics land here.
          </CardDescription>
        </CardHeader>
      </Card>
    </main>
  );
}
