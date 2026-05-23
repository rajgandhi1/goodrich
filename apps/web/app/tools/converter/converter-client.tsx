"use client";

import * as React from "react";
import { Calculator, Copy, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { convertUnits } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const groups = {
  length: {
    title: "Length",
    type: "length",
    pairs: [["in", "mm"], ["mm", "in"]],
  },
  pipe: {
    title: "DN / NPS",
    type: "pipe-size",
    pairs: [["dn", "nps"], ["nps", "dn"]],
  },
  pressure: {
    title: "Pressure",
    type: "pressure",
    pairs: [["psi", "bar"], ["bar", "psi"], ["psi", "mpa"], ["mpa", "psi"], ["bar", "mpa"], ["mpa", "bar"], ["kpa", "psi"], ["psi", "kpa"]],
  },
  rating: {
    title: "ASME Class / PN",
    type: "rating",
    pairs: [["class", "pn"], ["pn", "class"]],
  },
  temperature: {
    title: "Temperature",
    type: "temperature",
    pairs: [["c", "f"], ["f", "c"], ["c", "k"], ["k", "c"]],
  },
  torque: {
    title: "Torque",
    type: "torque",
    pairs: [["nm", "ftlb"], ["ftlb", "nm"], ["nm", "inlb"], ["inlb", "nm"]],
  },
  force: {
    title: "Force",
    type: "force",
    pairs: [["kn", "kgf"], ["kgf", "kn"], ["n", "lbf"], ["lbf", "n"]],
  },
} as const;

function Panel({ group }: { group: (typeof groups)[keyof typeof groups] }) {
  const [value, setValue] = React.useState("1");
  const [pair, setPair] = React.useState(group.pairs[0].join(":"));
  const [result, setResult] = React.useState("");

  async function run() {
    const [from, to] = pair.split(":");
    try {
      const response = await convertUnits(group.type, Number(value), from, to);
      setResult(response.display);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Conversion failed");
    }
  }

  React.useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pair]);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-base"><Calculator className="h-4 w-4" />{group.title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 p-3 md:grid-cols-[1fr_180px_auto_1fr_auto] md:items-end">
        <div className="space-y-1.5">
          <Label>Value</Label>
          <Input type="number" value={value} onChange={(event) => setValue(event.target.value)} onBlur={run} />
        </div>
        <div className="space-y-1.5">
          <Label>Units</Label>
          <Select value={pair} onValueChange={setPair}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {group.pairs.map(([from, to]) => <SelectItem key={`${from}:${to}`} value={`${from}:${to}`}>{from} to {to}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button size="sm" onClick={run}>
          <RefreshCw className="h-4 w-4" />
          Convert
        </Button>
        <div className="space-y-1.5">
          <Label>Result</Label>
          <Input value={result} readOnly />
        </div>
        <Button variant="secondary" size="sm" aria-label="Copy result" onClick={() => navigator.clipboard.writeText(result).then(() => toast.success("Copied"))}>
          <Copy className="h-4 w-4" />
        </Button>
      </CardContent>
    </Card>
  );
}

export function ConverterClient() {
  return (
    <Tabs defaultValue="length" className="space-y-3">
      <div className="rounded-lg border bg-card p-3 shadow-sm">
        <TabsList className="flex h-auto flex-wrap justify-start">
        {Object.entries(groups).map(([key, group]) => (
          <TabsTrigger key={key} value={key} className="gap-2">
            <Calculator className="h-4 w-4" />
            {group.title}
          </TabsTrigger>
        ))}
        </TabsList>
      </div>
      {Object.entries(groups).map(([key, group]) => (
        <TabsContent key={key} value={key}>
          <Panel group={group} />
        </TabsContent>
      ))}
    </Tabs>
  );
}
