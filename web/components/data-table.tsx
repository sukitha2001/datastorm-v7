"use client"

import * as React from "react"
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type Column,
  type ColumnDef,
  type ColumnFiltersState,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table"
import { z } from "zod"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronsLeft,
  ChevronLeft,
  ChevronRight,
  ChevronsRight,
  Columns3,
} from "lucide-react"

export const budgetSchema = z.object({
  Outlet_ID: z.string(),
  Distributor_ID: z.string(),
  Outlet_Type: z.string(),
  Outlet_Size: z.string(),
  Cooler_Count: z.number(),
  constraint_flag: z.number(),
  volume_cv: z.number(),
  historical_max_volume: z.number(),
  Maximum_Monthly_Liters: z.number(),
  incremental_volume: z.number(),
  Trade_Spend_LKR: z.number(),
  Spend_Type: z.enum(["discount", "merchandising", "promotional"]),
})

const typeColor: Record<string, string> = {
  discount:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  merchandising:
    "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  promotional:
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
}

const fmtMoney = (v: number) =>
  "LKR " + v.toLocaleString(undefined, { maximumFractionDigits: 0 })

function SortHeader({
  column,
  label,
  align = "left",
}: {
  column: Column<any>
  label: string
  align?: "left" | "right"
}) {
  const sorted = column.getIsSorted()
  return (
    <button
      onClick={() => column.toggleSorting(sorted === "asc")}
      className={`inline-flex items-center gap-1 text-xs font-medium hover:text-foreground ${
        align === "right" ? "justify-end w-full" : ""
      }`}
    >
      {label}
      {sorted === "asc" ? (
        <ArrowUp className="size-3" />
      ) : sorted === "desc" ? (
        <ArrowDown className="size-3" />
      ) : (
        <ArrowUpDown className="size-3 opacity-30" />
      )}
    </button>
  )
}

function InputFilter({ column }: { column: Column<any> }) {
  const [value, setValue] = React.useState("")
  React.useEffect(() => {
    const id = setTimeout(() => column.setFilterValue(value || undefined), 200)
    return () => clearTimeout(id)
  }, [value, column])
  return (
    <Input
      placeholder="Filter..."
      value={value}
      onChange={(e) => setValue(e.target.value)}
      className="h-7 text-xs mt-1"
    />
  )
}

function SelectFilter({
  column,
  options,
  placeholder = "All",
}: {
  column: Column<any>
  options: string[]
  placeholder?: string
}) {
  const filterValue = column.getFilterValue() as string | undefined
  const value = filterValue ?? "__all__"
  return (
    <Select
      value={value}
      onValueChange={(v) =>
        column.setFilterValue(v === "__all__" ? undefined : v)
      }
    >
      <SelectTrigger className="h-7 text-xs mt-1">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectItem value="__all__">All</SelectItem>
          {options.map((opt) => (
            <SelectItem key={opt} value={opt}>
              {opt}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

function RangeFilter({
  column,
  min,
  max,
  step,
}: {
  column: Column<any>
  min: number
  max: number
  step?: number
}) {
  const [lo, setLo] = React.useState("")
  const [hi, setHi] = React.useState("")
  React.useEffect(() => {
    const current = column.getFilterValue() as [number, number] | undefined
    setLo(current?.[0] !== undefined ? String(current[0]) : "")
    setHi(current?.[1] !== undefined ? String(current[1]) : "")
  }, [column])
  React.useEffect(() => {
    const id = setTimeout(() => {
      const loNum = lo === "" ? -Infinity : Number(lo)
      const hiNum = hi === "" ? Infinity : Number(hi)
      column.setFilterValue(
        lo !== "" || hi !== ""
          ? [loNum, hiNum]
          : undefined
      )
    }, 200)
    return () => clearTimeout(id)
  }, [lo, hi, column])
  return (
    <div className="flex items-center gap-1 mt-1">
      <Input
        type="number"
        placeholder={String(min)}
        value={lo}
        onChange={(e) => setLo(e.target.value)}
        min={min}
        max={max}
        step={step}
        className="h-7 w-[68px] text-[10px]"
      />
      <span className="text-[10px] text-muted-foreground">–</span>
      <Input
        type="number"
        placeholder={String(max)}
        value={hi}
        onChange={(e) => setHi(e.target.value)}
        min={min}
        max={max}
        step={step}
        className="h-7 w-[68px] text-[10px]"
      />
    </div>
  )
}

function SpendTypeBadge({ type }: { type: string }) {
  return (
    <Badge
      variant="outline"
      className={`text-[10px] tracking-wider uppercase ${typeColor[type] ?? ""}`}
    >
      {type}
    </Badge>
  )
}

const columns: ColumnDef<z.infer<typeof budgetSchema>>[] = [
  {
    accessorKey: "Outlet_ID",
    header: ({ column }) => <SortHeader column={column} label="Outlet" />,
    cell: ({ row }) => (
      <span className="font-mono text-xs">{row.original.Outlet_ID}</span>
    ),
    enableHiding: false,
    enableColumnFilter: true,
    filterFn: "includesString",
  },
  {
    accessorKey: "Outlet_Type",
    enableColumnFilter: true,
    filterFn: "equalsString",
    header: ({ column }) => <SortHeader column={column} label="Type" />,
    cell: ({ row }) => (
      <span className="text-xs text-muted-foreground">{row.original.Outlet_Type}</span>
    ),
  },
  {
    accessorKey: "Distributor_ID",
    header: ({ column }) => <SortHeader column={column} label="Distributor" />,
    enableColumnFilter: true,
    filterFn: "equalsString",
    cell: ({ row }) => (
      <span className="font-mono text-xs">{row.original.Distributor_ID}</span>
    ),
  },
  {
    accessorKey: "Outlet_Size",
    header: ({ column }) => <SortHeader column={column} label="Size" />,
    enableColumnFilter: true,
    filterFn: "equalsString",
    cell: ({ row }) => (
      <span className="text-xs text-muted-foreground">{row.original.Outlet_Size}</span>
    ),
  },
  {
    accessorKey: "Cooler_Count",
    header: ({ column }) => <SortHeader column={column} label="Coolers" />,
    filterFn: "inNumberRange",
    cell: ({ row }) => (
      <span className="text-xs tabular-nums">{row.original.Cooler_Count}</span>
    ),
  },
  {
    accessorKey: "constraint_flag",
    header: ({ column }) => <SortHeader column={column} label="Cnstr" />,
    enableColumnFilter: true,
    filterFn: "equalsString",
    cell: ({ row }) => {
      const v = row.original.constraint_flag
      return (
        <span
          className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
            v
              ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
              : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
          }`}
        >
          {v ? "YES" : "no"}
        </span>
      )
    },
  },
  {
    accessorKey: "volume_cv",
    header: ({ column }) => <SortHeader column={column} label="CV" />,
    filterFn: "inNumberRange",
    cell: ({ row }) => (
      <span className="text-xs tabular-nums">{row.original.volume_cv.toFixed(3)}</span>
    ),
  },
  {
    id: "upside",
    accessorKey: "incremental_volume",
    header: ({ column }) => (
      <SortHeader column={column} label="Upside (L)" align="right" />
    ),
    filterFn: "inNumberRange",
    cell: ({ row }) => (
      <div className="text-right text-xs tabular-nums">
        {row.original.incremental_volume.toLocaleString()}
      </div>
    ),
  },
  {
    accessorKey: "Spend_Type",
    header: ({ column }) => <SortHeader column={column} label="Spend Type" />,
    enableColumnFilter: true,
    filterFn: "equalsString",
    cell: ({ row }) => <SpendTypeBadge type={row.original.Spend_Type} />,
  },
  {
    accessorKey: "Trade_Spend_LKR",
    header: ({ column }) => (
      <SortHeader column={column} label="Trade Spend (LKR)" align="right" />
    ),
    filterFn: "inNumberRange",
    cell: ({ row }) => (
      <div className="text-right font-medium tabular-nums">
        {fmtMoney(Math.round(row.original.Trade_Spend_LKR))}
      </div>
    ),
  },
  {
    id: "share",
    header: () => <div className="text-right text-xs font-medium">Share</div>,
    cell: ({ row, table }) => {
      const total = table
        .getFilteredRowModel()
        .rows.reduce((s, r) => s + r.original.Trade_Spend_LKR, 0)
      return (
        <div className="text-right text-muted-foreground tabular-nums">
          {((row.original.Trade_Spend_LKR / total) * 100).toFixed(2)}%
        </div>
      )
    },
  },
]

function getUniqueValues(data: any[], key: string): string[] {
  const set = new Set<string>()
  for (const row of data) {
    const v = row[key]
    if (v != null && v !== "") set.add(String(v))
  }
  return Array.from(set).sort()
}

function columnFilter(column: Column<any>, data: any[]) {
  const id = column.id
  if (id === "Outlet_ID") return <InputFilter column={column} />
  if (id === "Distributor_ID")
    return (
      <SelectFilter
        column={column}
        options={getUniqueValues(data, "Distributor_ID")}
      />
    )
  if (id === "Outlet_Type")
    return (
      <SelectFilter
        column={column}
        options={getUniqueValues(data, "Outlet_Type")}
      />
    )
  if (id === "Outlet_Size")
    return (
      <SelectFilter
        column={column}
        options={getUniqueValues(data, "Outlet_Size")}
      />
    )
  if (id === "Spend_Type")
    return (
      <SelectFilter
        column={column}
        options={getUniqueValues(data, "Spend_Type")}
      />
    )
  if (id === "constraint_flag")
    return (
      <SelectFilter
        column={column}
        options={getUniqueValues(data, "constraint_flag")}
      />
    )
  if (id === "Cooler_Count")
    return <RangeFilter column={column} min={0} max={50} step={1} />
  if (id === "volume_cv")
    return <RangeFilter column={column} min={0} max={5} step={0.01} />
  if (id === "upside" || id === "incremental_volume")
    return <RangeFilter column={column} min={0} max={50000} step={10} />
  if (id === "Trade_Spend_LKR")
    return <RangeFilter column={column} min={0} max={150000} step={100} />
  return null
}

export function DataTable({ data }: { data: z.infer<typeof budgetSchema>[] }) {
  const [rowSelection, setRowSelection] = React.useState({})
  const [columnVisibility, setColumnVisibility] =
    React.useState<VisibilityState>({
      constraint_flag: false,
      volume_cv: false,
      upside: false,
    })
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    []
  )
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [pagination, setPagination] = React.useState({
    pageIndex: 0,
    pageSize: 10,
  })

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnVisibility,
      rowSelection,
      columnFilters,
      pagination,
    },
    getRowId: (row) => row.Outlet_ID,
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const totalBudget = data.reduce((s, b) => s + b.Trade_Spend_LKR, 0)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2 px-4 lg:px-6">
        <div className="text-sm text-muted-foreground">
          {data.length.toLocaleString()} outlets ·{" "}
          {fmtMoney(Math.round(totalBudget))} total
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-7 gap-1 text-xs">
              <Columns3 className="size-3" />
              Columns
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {table
              .getAllColumns()
              .filter((c) => c.getCanHide())
              .map((c) => (
                <DropdownMenuCheckboxItem
                  key={c.id}
                  checked={c.getIsVisible()}
                  onCheckedChange={(v) => c.toggleVisibility(!!v)}
                >
                  {c.id}
                </DropdownMenuCheckboxItem>
              ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-muted">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id} colSpan={header.colSpan}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={`filter-${headerGroup.id}`}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.column.getCanFilter()
                      ? columnFilter(header.column, data)
                      : null}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between px-4">
        <div className="hidden flex-1 text-sm text-muted-foreground lg:flex">
          {table.getFilteredSelectedRowModel().rows.length} of{" "}
          {table.getFilteredRowModel().rows.length} row(s) selected.
        </div>
        <div className="flex w-full items-center gap-8 lg:w-fit">
          <div className="hidden items-center gap-2 lg:flex">
            <label htmlFor="rows-per-page" className="text-sm font-medium">
              Rows per page
            </label>
            <Select
              value={`${table.getState().pagination.pageSize}`}
              onValueChange={(value) => {
                table.setPageSize(Number(value))
              }}
            >
              <SelectTrigger size="sm" className="w-20" id="rows-per-page">
                <SelectValue
                  placeholder={table.getState().pagination.pageSize}
                />
              </SelectTrigger>
              <SelectContent side="top">
                <SelectGroup>
                  {[10, 20, 30, 40, 50].map((pageSize) => (
                    <SelectItem key={pageSize} value={`${pageSize}`}>
                      {pageSize}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-center text-sm font-medium">
            Page {table.getState().pagination.pageIndex + 1} of{" "}
            {table.getPageCount()}
          </div>
          <div className="ml-auto flex items-center gap-2 lg:ml-0">
            <Button
              variant="outline"
              className="hidden h-8 w-8 p-0 lg:flex"
              onClick={() => table.setPageIndex(0)}
              disabled={!table.getCanPreviousPage()}
            >
              <span className="sr-only">Go to first page</span>
              <ChevronsLeft />
            </Button>
            <Button
              variant="outline"
              className="size-8"
              size="icon"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <span className="sr-only">Go to previous page</span>
              <ChevronLeft />
            </Button>
            <Button
              variant="outline"
              className="size-8"
              size="icon"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              <span className="sr-only">Go to next page</span>
              <ChevronRight />
            </Button>
            <Button
              variant="outline"
              className="hidden size-8 lg:flex"
              size="icon"
              onClick={() => table.setPageIndex(table.getPageCount() - 1)}
              disabled={!table.getCanNextPage()}
            >
              <span className="sr-only">Go to last page</span>
              <ChevronsRight />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
